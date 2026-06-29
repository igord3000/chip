"""Orchestrator - coordinates main agent and subagents."""
import json
from typing import Optional
from dataclasses import dataclass

from chip.config import AgentConfig, load_config
from chip.llm import LLMClient
from chip.tools import ToolRegistry
from chip.router import QueryRouter, QueryType
from chip.subagent import SubagentManager
from chip.logger import get_logger


@dataclass
class OrchestratorResult:
    success: bool
    answer: str
    subtasks: list[str] = None
    subtask_results: list[str] = None


class Orchestrator:
    """Orchestrator that decides when to use subagents."""
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or load_config()
        self.llm = LLMClient(self.config.llm)
        self.tools = ToolRegistry(bash_timeout=self.config.bash_timeout)
        self.router = QueryRouter()
        self.subagent_manager = SubagentManager(self.config)
        self.log = get_logger()
    
    def should_use_subagents(self, query: str) -> bool:
        """Determine if query needs parallel subagents."""
        query_lower = query.lower()
        
        # Complex queries that benefit from parallel execution
        indicators = [
            "и также", "а также", "кроме того", "помимо этого",
            "параллельно", "одновременно", "сравни", "сделай несколько",
            "research", "compare", "analyze multiple"
        ]
        
        for indicator in indicators:
            if indicator in query_lower:
                return True
        
        # If query has multiple distinct parts
        if query_lower.count("?") > 1:
            return True
        
        return False
    
    def split_into_subtasks(self, query: str) -> list[str]:
        """Split complex query into subtasks."""
        # Simple heuristic: split by "и", "а также", etc.
        parts = []
        
        for separator in [" и ", " а также ", " кроме того ", " также "]:
            if separator in query.lower():
                parts = [p.strip() for p in query.split(separator) if p.strip()]
                break
        
        if not parts:
            parts = [query]
        
        return parts
    
    def execute(self, query: str, callback=None) -> OrchestratorResult:
        """Execute query, using subagents if needed."""
        self.log.info(f"Orchestrator: processing '{query}'")
        
        # Check if we should use subagents
        if self.should_use_subagents(query):
            self.log.info("Query is complex - using subagents")
            return self._execute_with_subagents(query, callback)
        else:
            self.log.info("Query is simple - single execution")
            return self._execute_single(query, callback)
    
    def _execute_single(self, query: str, callback=None) -> OrchestratorResult:
        """Execute single query."""
        query_type = self.router.route(query)
        hint = self.router.get_prompt_hint(query_type)
        
        messages = [
            {"role": "system", "content": "Ты помощник. Отвечай кратко и по существу на русском. Не показывай ссылки - показывай данные. Если вызвал инструмент - обобщи результат."},
            {"role": "user", "content": f"{query}\n\n[Подсказка: {hint}]" if hint else query}
        ]
        
        self.log.info(f"Single execution: query_type={query_type.value}")
        
        try:
            response = self.llm.chat(messages, self.tools.to_openai_tools())
            
            # Handle tool calls
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    func_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    
                    self.log.info(f"Tool call: {func_name}")
                    result = self.tools.call(func_name, arguments)
                    
                    messages.append({
                        "role": "assistant",
                        "content": response.content or None,
                        "tool_calls": [tool_call]
                    })
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call["id"],
                        "content": result.output
                    })
                    
                    # Auto-pipeline: web_search -> web_fetch
                    if func_name == "web_search" and result.success:
                        import re
                        urls = re.findall(r'https?://[^\s\)]+', result.output)
                        if urls:
                            fetch_result = self.tools.call("web_fetch", {"url": urls[0], "format": "text"})
                            if fetch_result.success:
                                truncated = fetch_result.output[:2000]
                                messages.append({
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [{
                                        "id": f"auto_{tool_call['id']}",
                                        "type": "function",
                                        "function": {"name": "web_fetch", "arguments": json.dumps({"url": urls[0]})}
                                    }]
                                })
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": f"auto_{tool_call['id']}",
                                    "content": truncated
                                })
                
                # Get final answer after tool calls
                messages.append({
                    "role": "user",
                    "content": "Теперь дай финальный ответ на основе полученных данных. Кратко и по существу."
                })
                response = self.llm.chat(messages)
            
            # If still no content, try one more time
            if not response.content:
                messages.append({
                    "role": "user",
                    "content": "Дай ответ на вопрос. Не вызывай инструменты."
                })
                response = self.llm.chat(messages)
            
            return OrchestratorResult(
                success=True,
                answer=response.content or "Не удалось получить ответ"
            )
            
        except Exception as e:
            self.log.error(f"Execution error: {e}", e)
            return OrchestratorResult(success=False, answer=f"Ошибка: {e}")
    
    def _execute_with_subagents(self, query: str, callback=None) -> OrchestratorResult:
        """Execute query using parallel subagents."""
        subtasks = self.split_into_subtasks(query)
        self.log.info(f"Split into {len(subtasks)} subtasks: {subtasks}")
        
        # Execute subtasks in parallel
        results = self.subagent_manager.run_parallel(subtasks)
        
        # Collect results
        subtask_results = []
        for i, result in enumerate(results):
            status = "✓" if result.success else "✗"
            subtask_results.append(f"{status} {subtasks[i]}: {result.output[:200]}")
        
        # Synthesize final answer
        combined_results = "\n".join(subtask_results)
        
        messages = [
            {"role": "system", "content": "Ты помощник. Обобщи результаты подзадач в один ответ на русском."},
            {"role": "user", "content": f"Оригинальный запрос: {query}\n\nРезультаты подзадач:\n{combined_results}"}
        ]
        
        try:
            response = self.llm.chat(messages)
            return OrchestratorResult(
                success=True,
                answer=response.content or combined_results,
                subtasks=subtasks,
                subtask_results=subtask_results
            )
        except Exception as e:
            return OrchestratorResult(
                success=True,
                answer=combined_results,
                subtasks=subtasks,
                subtask_results=subtask_results
            )
