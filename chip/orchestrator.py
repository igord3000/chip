"""Orchestrator - routes LLM tool calls to real APIs."""
import json
import time
from typing import Optional, Callable
from dataclasses import dataclass, field

from chip.config import AgentConfig, load_config
from chip.llm import LLMClient
from chip.tools import ToolRegistry
from chip.router import QueryRouter, QueryType
from chip.logger import get_logger


@dataclass
class OrchestratorResult:
    success: bool
    answer: str
    tools_called: list[str] = field(default_factory=list)
    duration_ms: int = 0


class Orchestrator:
    """
    Orchestrator follows the golden rule:
    - LLM THINKS: chooses function + fills arguments (generates JSON)
    - Orchestrator ACTS: calls real API with that JSON
    - LLM ANSWERS: converts raw data to human-readable text
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or load_config()
        self.llm = LLMClient(self.config.llm)
        self.tools = ToolRegistry(bash_timeout=self.config.bash_timeout)
        self.router = QueryRouter()
        self.log = get_logger()
    
    def execute(self, query: str, callback: Optional[Callable] = None) -> OrchestratorResult:
        """Execute query following the orchestrator pattern."""
        start_time = time.time()
        tools_called = []
        
        self.log.info(f"Orchestrator: '{query}'")
        
        # Step 1: Route query
        query_type = self.router.route(query)
        hint = self.router.get_prompt_hint(query_type)
        self.log.info(f"Query type: {query_type.value}")
        
        if callback:
            callback(f"Тип запроса: {query_type.value}")
        
        # Step 2: Send to LLM with tools
        messages = [
            {"role": "system", "content": self._get_system_prompt(query_type)},
            {"role": "user", "content": f"{query}\n\n[Hint: {hint}]" if hint else query}
        ]
        
        try:
            # LLM THINKS: generates tool call JSON
            response = self.llm.chat(messages, self.tools.to_openai_tools())
            self.log.info(f"LLM response: content={len(response.content or '')} chars, tools={len(response.tool_calls)}")
            
            # Step 3: If LLM wants to call tools - ORCHESTRATOR ACTS
            if response.tool_calls:
                for tool_call in response.tool_calls:
                    func_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    
                    self.log.info(f"Tool call: {func_name}({arguments})")
                    if callback:
                        callback(f"Вызов: {func_name}")
                    
                    # Orchestrator executes the real API
                    result = self.tools.call(func_name, arguments)
                    tools_called.append(func_name)
                    
                    self.log.info(f"Tool result: {result.output[:100]}...")
                    if callback:
                        callback(f"Результат: {result.output[:150]}...")
                    
                    # Add to context
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
                        first_url = self._extract_first_url(result.output)
                        if first_url:
                            self.log.info(f"Auto-fetch: {first_url}")
                            if callback:
                                callback(f"Загрузка: {first_url}")
                            
                            fetch_result = self.tools.call("web_fetch", {"url": first_url, "format": "text"})
                            if fetch_result.success:
                                messages.append({
                                    "role": "assistant",
                                    "content": None,
                                    "tool_calls": [{
                                        "id": f"auto_{tool_call['id']}",
                                        "type": "function",
                                        "function": {"name": "web_fetch", "arguments": json.dumps({"url": first_url})}
                                    }]
                                })
                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": f"auto_{tool_call['id']}",
                                    "content": fetch_result.output[:2000]
                                })
                                tools_called.append("web_fetch")
                
                # Step 4: LLM ANSWERS - converts data to human text
                messages.append({
                    "role": "user",
                    "content": "Дай финальный ответ на основе полученных данных. Кратко и по существу. Не показывай ссылки."
                })
                response = self.llm.chat(messages)
            
            # If still no content, ask LLM to answer
            if not response.content:
                messages.append({
                    "role": "user",
                    "content": "Дай ответ на вопрос. Не вызывай инструменты."
                })
                response = self.llm.chat(messages)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            return OrchestratorResult(
                success=True,
                answer=response.content or "Не удалось получить ответ",
                tools_called=tools_called,
                duration_ms=duration_ms
            )
            
        except Exception as e:
            self.log.error(f"Orchestrator error: {e}", e)
            duration_ms = int((time.time() - start_time) * 1000)
            return OrchestratorResult(
                success=False,
                answer=f"Ошибка: {e}",
                duration_ms=duration_ms
            )
    
    def _get_system_prompt(self, query_type: QueryType) -> str:
        """Get system prompt based on query type."""
        prompts = {
            QueryType.CONVERSATION: "Ты помощник. Отвечай дружелюбно и кратко.",
            QueryType.KNOWLEDGE: "Ты помощник. Отвечай из своих знаний, кратко.",
            QueryType.CURRENT_DATA: """Ты помощник с доступом к актуальным данным.

ПРАВИЛА:
1. Сначала вызови web_search для поиска
2. Затем web_fetch для чтения страницы
3. Извлеки КОКРЕТНЫЕ данные: температуру, дату, числа
4. Дай ответ на основе ПОЛУЧЕННЫХ данных, а не из своих знаний
5. Не пиши "у меня нет доступа" - у тебя есть инструменты!
6. Формат ответа: цифры, факты, кратко""",
            QueryType.CODE: "Ты coding-помощник. Используй инструменты для написания и запуска кода.",
            QueryType.FILE_OP: "Ты помощник. Используй инструменты для работы с файлами.",
            QueryType.SEARCH: "Ты помощник. Найди информацию и кратко изложи ключевые факты.",
        }
        return prompts.get(query_type, "Ты помощник. Отвечай кратко и по существу.")
    
    def _extract_first_url(self, text: str) -> Optional[str]:
        """Extract first URL from text."""
        import re
        urls = re.findall(r'https?://[^\s\)]+', text)
        return urls[0] if urls else None
