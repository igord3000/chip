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
- bash: выполнять команды
- read_file: читать файлы
- write_file: записывать файлы
- list_files: список файлов
- web_search: искать в интернете
- web_fetch: читать страницы
- download: скачивать файлы

ПРАВИЛА ОТВЕТОВ:
1. Отвечай СТРУКТУРИРОВАННО — с переносами строк
2. Используй списки с • или нумерацией
3. Разделяй секции пустой строкой
4. Не пиши всё в одну строку

ПРИМЕР ХОРОШЕГО ОТВЕТА:
Python — язык программирования.

• Тип: высокоуровневый
• Год создания: 1991
• Автор: Гвидо ван Россум

Используется для веб-разработки, анализа данных и AI.

ВАЖНО ДЛЯ УТОЧНЕНИЙ:
Если пользователь задаёт уточняющий вопрос (например "а у диллеров?", "а где купить?", "а какие модели?"):
- ПОСМОТРИ на предыдущий контекст диалога
- ПОНЯМИ что именно уточняется
- Сформулируй ПОЛНЫЙ запрос для поиска
- Например: "а у диллеров?" → "цены на Веста у дилеров в миассе"

ПРАВИЛА ИНСТРУМЕНТОВ:
- "что такое X" → ответь из знаний
- "найди/поищи" → web_search
- "прочитай URL" → web_fetch
- "погода/курс/новости" → web_search → web_fetch
- "напиши код" → write_file
- "прочитай файл" → read_file"""
    
    def _preprocess_query(self, query: str, history: Optional[list[dict]] = None) -> str:
        """Preprocess query to handle follow-ups."""
        if not history:
            return query
        
        # Get last assistant message for context
        last_assistant = ""
        for msg in reversed(history):
            if msg.get("role") == "assistant":
                last_assistant = msg.get("content", "")
                break
        
        if not last_assistant:
            return query
        
        # Check if this is a follow-up question
        follow_up_indicators = [
            "а ", "а что", "а где", "а как", "а когда",
            "а какие", "а какой", "а какая", "а какое",
            "а у ", "а в ", "а на ", "а для ",
            "расскажи еще", "подробнее", "детальнее",
        ]
        
        is_follow_up = any(indicator in query.lower() for indicator in follow_up_indicators)
        
        if is_follow_up:
            # Prepend context from last exchange
            context = f"Контекст: {last_assistant[:200]}\n\nУточнение: {query}"
            self.log.info(f"Follow-up detected, adding context")
            return context
        
        return query
    
    def execute(self, query: str, callback: Optional[Callable] = None, history: Optional[list[dict]] = None) -> AgentResult:
        """Execute any query using LLM + tools."""
        start_time = time.time()
        tools_called = []
        
        self.log.info(f"Agent: '{query}'")
        
        if callback:
            callback("Обработка...")
        
        # Build messages with context
        messages = [
            {"role": "system", "content": self.system_prompt}
        ]
        
        # Add conversation history (last 8 exchanges = 16 messages)
        if history:
            messages.extend(history[-16:])
        
        # Preprocess query for follow-ups
        processed_query = self._preprocess_query(query, history)
        messages.append({"role": "user", "content": processed_query})
        
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
