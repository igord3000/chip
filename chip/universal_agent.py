"""Universal Agent - works with any query without manual routing."""
import json
import time
from typing import Optional, Callable
from dataclasses import dataclass, field

from chip.config import AgentConfig, load_config
from chip.llm import LLMClient
from chip.tools import ToolRegistry
from chip.logger import get_logger
from chip.data_extractor import DataExtractor


@dataclass
class AgentResult:
    success: bool
    answer: str
    tools_called: list[str] = field(default_factory=list)
    duration_ms: int = 0
    subagents_used: int = 0


class UniversalAgent:
    """
    Universal agent that works with ANY query.
    
    Architecture (inspired by AutoGen):
    - LLM decides WHAT to do (not router)
    - LLM decides WHICH tools to use
    - Agent executes tools
    - LLM formats the answer
    
    Key principle: LLM does the thinking, agent does the acting.
    """
    
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or load_config()
        self.llm = LLMClient(self.config.llm)
        self.tools = ToolRegistry(bash_timeout=self.config.bash_timeout)
        self.log = get_logger()
        self.extractor = DataExtractor()
        
        self.system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build a single flexible system prompt."""
        return """Ты — Chip, умный AI-ассистент с доступом к инструментам.

ИНСТРУМЕНТЫ:
- bash: выполнять команды shell
- read_file: читать файлы
- write_file: записывать файлы
- list_files: список файлов
- web_search: искать в интернете
- web_fetch: читать страницы по URL
- download: скачивать файлы

ПРАВИЛА:
1. Определи что хочет пользователь
2. Выбери подходящий инструмент
3. Вызови инструмент
4. Обработай результат
5. Дай краткий ответ

ВАЖНО:
- Для вопросов "что такое X" — отвечай из знаний
- Для "найди/поищи" — используй web_search
- Для "прочитай URL" — используй web_fetch
- Для "погода/курс/новости" — сначала web_search, потом web_fetch
- Для "напиши код/файл" — используй write_file
- Для "прочитай файл" — используй read_file

Отвечай кратко на русском. Не показывай ссылки — показывай данные."""
    
    def execute(self, query: str, callback: Optional[Callable] = None) -> AgentResult:
        """Execute any query using LLM + tools."""
        start_time = time.time()
        tools_called = []
        
        self.log.info(f"Agent: '{query}'")
        
        if callback:
            callback("Обработка запроса...")
        
        # Build messages
        messages = [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": query}
        ]
        
        try:
            # Main loop: LLM decides, agent executes
            for turn in range(5):  # Max 5 tool calls
                self.log.info(f"Turn {turn + 1}: Calling LLM...")
                
                # LLM THINKS
                response = self.llm.chat(messages, self.tools.to_openai_tools())
                
                self.log.info(f"LLM: content={len(response.content or '')} chars, tools={len(response.tool_calls)}")
                
                # If no tool calls, LLM is done
                if not response.tool_calls:
                    if response.content:
                        return AgentResult(
                            success=True,
                            answer=response.content,
                            tools_called=tools_called,
                            duration_ms=int((time.time() - start_time) * 1000)
                        )
                    else:
                        # Ask LLM to answer
                        messages.append({"role": "user", "content": "Дай ответ на вопрос."})
                        continue
                
                # AGENT ACTS: execute each tool call
                for tool_call in response.tool_calls:
                    func_name = tool_call["function"]["name"]
                    arguments = json.loads(tool_call["function"]["arguments"])
                    
                    self.log.info(f"Tool: {func_name}({arguments})")
                    if callback:
                        callback(f"Вызов: {func_name}")
                    
                    # Execute tool
                    result = self.tools.call(func_name, arguments)
                    tools_called.append(func_name)
                    
                    self.log.info(f"Result: {result.output[:100]}...")
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
                        "content": result.output[:3000]  # Limit context
                    })
                    
                    # Auto-pipeline for search
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
                
                # After tools, ask LLM to answer
                messages.append({
                    "role": "user",
                    "content": "На основе полученных данных дай краткий ответ."
                })
            
            # If we exhausted turns, return what we have
            return AgentResult(
                success=True,
                answer=response.content if response.content else "Не удалось получить ответ",
                tools_called=tools_called,
                duration_ms=int((time.time() - start_time) * 1000)
            )
            
        except Exception as e:
            self.log.error(f"Agent error: {e}", e)
            return AgentResult(
                success=False,
                answer=f"Ошибка: {e}",
                duration_ms=int((time.time() - start_time) * 1000)
            )
    
    def _extract_first_url(self, text: str) -> Optional[str]:
        """Extract first URL from text."""
        import re
        urls = re.findall(r'https?://[^\s\)]+', text)
        return urls[0] if urls else None
