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
from chip.data_extractor import DataExtractor


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
        self.extractor = DataExtractor()
    
    def _extract_city(self, query: str) -> Optional[str]:
        """Extract city name from query."""
        import re
        # Common patterns for city in Russian
        patterns = [
            r'в ([А-Яа-яёЁ]+)',
            r'в ([А-Яа-яёЁ]+(?:-[А-Яа-яёЁ]+)?)',
            r'на ([А-Яа-яёЁ]+)',
        ]
        for pattern in patterns:
            match = re.search(pattern, query)
            if match:
                city = match.group(1)
                # Filter out time-related words
                if city.lower() not in ['неделю', 'месяц', 'завтра', 'сегодня', 'сейчас', 'утро', 'вечер', 'ночь']:
                    return city
        return None
    
    def _extract_time_period(self, query: str) -> str:
        """Extract time period from query."""
        query_lower = query.lower()
        
        if any(w in query_lower for w in ['завтра', 'tomorrow']):
            return 'tomorrow'
        elif any(w in query_lower for w in ['на неделю', 'неделю', 'week']):
            return 'week'
        elif any(w in query_lower for w in ['на месяц', 'месяц', 'month']):
            return 'month'
        elif any(w in query_lower for w in ['сегодня', 'сейчас', 'today', 'now']):
            return 'today'
        else:
            return 'today'  # Default to current weather
    
    def _get_wttr_url(self, city: str, days: int = 1) -> str:
        """Get wttr.in URL for weather."""
        if days == 1:
            return f"https://wttr.in/{city}?format=j1"
        else:
            return f"https://wttr.in/{city}?format=j1"
    
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
        
        # Special handling for weather queries
        if query_type == QueryType.CURRENT_DATA:
            city = self._extract_city(query)
            if city and any(w in query.lower() for w in ['погод', 'weather']):
                time_period = self._extract_time_period(query)
                return self._handle_weather(city, time_period, query, callback)
        
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
                    "content": "На основе полученных данных дай КОКРЕТНЫЙ ответ. Например: 'Температура +18°C, ветер 3 м/с, облачно'. Не пиши 'прогнозируется' - пиши ТОЧНЫЕ данные."
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
    
    def _handle_weather(self, city: str, time_period: str, query: str, callback: Optional[Callable] = None) -> OrchestratorResult:
        """Handle weather queries."""
        import time
        import re
        start_time = time.time()
        
        self.log.info(f"Weather request for city: {city}, period: {time_period}")
        if callback:
            period_names = {'today': 'сейчас', 'tomorrow': 'завтра', 'week': 'на неделю', 'month': 'на месяц'}
            callback(f"Город: {city}, период: {period_names.get(time_period, time_period)}")
        
        try:
            # Build search query based on time period
            if time_period == 'tomorrow':
                search_query = f"погода в {city} завтра прогноз температура"
            elif time_period == 'week':
                search_query = f"погода в {city} на неделю прогноз температура"
            elif time_period == 'month':
                search_query = f"погода в {city} на месяц прогноз температура"
            else:
                search_query = f"погода в {city} сейчас температура"
            
            self.log.info(f"Searching: {search_query}")
            if callback:
                period_names = {'today': 'сейчас', 'tomorrow': 'завтра', 'week': 'на неделю', 'month': 'на месяц'}
                callback(f"Поиск погоды в {city} {period_names.get(time_period, '')}...")
            
            search_result = self.tools.call("web_search", {"query": search_query, "num_results": 5})
            
            if not search_result.success:
                return OrchestratorResult(
                    success=False,
                    answer=f"Не удалось найти погоду для {city}"
                )
            
            # Check if search results contain weather data
            weather_data = self._extract_weather_from_search(search_result.output, city, time_period)
            
            # If no data extracted (e.g., for tomorrow/week/month), fetch the page
            if 'Не удалось' in weather_data or len(weather_data) < 100:
                if callback:
                    callback(f"Загрузка страницы с прогнозом...")
                
                first_url = self._extract_first_url(search_result.output)
                if first_url:
                    fetch_result = self.tools.call("web_fetch", {"url": first_url, "format": "text"})
                    if fetch_result.success:
                        weather_data = self._extract_weather_from_search(fetch_result.output, city, time_period)
            
            duration_ms = int((time.time() - start_time) * 1000)
            
            return OrchestratorResult(
                success=True,
                answer=weather_data,
                tools_called=["web_search"],
                duration_ms=duration_ms
            )
            
        except Exception as e:
            self.log.error(f"Weather error: {e}", e)
            return OrchestratorResult(
                success=False,
                answer=f"Ошибка при получении погоды: {e}"
            )
    
    def _extract_weather_from_search(self, search_text: str, city: str, time_period: str) -> str:
        """Extract weather data from search results."""
        import re
        
        lines = search_text.split('\n')
        weather_info = []
        
        for line in lines:
            line = line.strip()
            
            # Look for temperature
            temp_match = re.search(r'температура[^+]*([+-]?\d+)', line, re.IGNORECASE)
            if temp_match:
                weather_info.append(f"Температура: +{temp_match.group(1)}°C")
            
            # Look for "feels like"
            feels_match = re.search(r'ощущается[^+]*([+-]?\d+)', line, re.IGNORECASE)
            if feels_match:
                weather_info.append(f"Ощущается как: +{feels_match.group(1)}°C")
            
            # Look for wind
            wind_match = re.search(r'ветер[^0-9]*(\d+[,.]?\d*)\s*(м/с|км/ч)', line, re.IGNORECASE)
            if wind_match:
                weather_info.append(f"Ветер: {wind_match.group(1)} {wind_match.group(2)}")
            
            # Look for humidity
            hum_match = re.search(r'влажность[^0-9]*(\d+)%', line, re.IGNORECASE)
            if hum_match:
                weather_info.append(f"Влажность: {hum_match.group(1)}%")
            
            # Look for pressure
            pres_match = re.search(r'давление[^0-9]*(\d+)\s*(мм|гПа|hPa)', line, re.IGNORECASE)
            if pres_match:
                weather_info.append(f"Давление: {pres_match.group(1)} {pres_match.group(2)}")
            
            # Look for weather condition
            for condition in ['облачно с прояснениями', 'облачно', 'ясно', 'дождь', 'снег', 'пасмурно', 'гроза', 'ливень']:
                if condition in line.lower():
                    weather_info.append(f"Погода: {condition}")
                    break
        
        if weather_info:
            # Remove duplicates
            seen = set()
            unique_info = []
            for item in weather_info:
                if item not in seen:
                    seen.add(item)
                    unique_info.append(item)
            
            # Add time period header
            period_names = {'today': 'сейчас', 'tomorrow': 'завтра', 'week': 'на неделю', 'month': 'на месяц'}
            header = f"Погода в {city} {period_names.get(time_period, '')}:"
            
            return header + "\n" + "\n".join(unique_info)
        
        # If no structured data found, return raw snippet
        for line in lines:
            if 'температура' in line.lower() or 'погод' in line.lower():
                return f"Погода в {city}:\n{line.strip()[:300]}"
        
        return f"Не удалось извлечь данные о погоде в {city}"
    
    def _get_system_prompt(self, query_type: QueryType) -> str:
        """Get system prompt based on query type."""
        prompts = {
            QueryType.CONVERSATION: "Ты помощник. Отвечай дружелюбно и кратко.",
            QueryType.KNOWLEDGE: "Ты помощник. Отвечай из своих знаний, кратко.",
            QueryType.CURRENT_DATA: """Ты помощник с доступом к актуальным данным.

ВАЖНО: Используй инструменты для получения данных!

Для погоды:
1. Вызови web_search для поиска
2. Вызови web_fetch для чтения страницы
3. Извлеки ТОЧНЫЕ данные: температуру, ветер, давление
4. Ответь КОНКРЕТНО: "Температура +18°C, ветер 3 м/с, облачно"

Например: "Сейчас в Миассе +10°C, ясно, ветер 2 м/с"
НЕ пиши "прогнозируется" - пиши ТО ЧТО ЕСТЬ в данных!""",
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
