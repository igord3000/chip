"""Query router — determines how to handle different types of queries."""
import re
from enum import Enum
from typing import Optional


class QueryType(Enum):
    CONVERSATION = "conversation"    # привет, анекдот, как дела
    KNOWLEDGE = "knowledge"          # что такое Python, объясни概念
    CURRENT_DATA = "current_data"    # погода, курсы, новости
    CODE = "code"                    # напиши код, создай файл
    FILE_OP = "file_op"              # прочитай файл, покажи код
    SEARCH = "search"                # найди информацию


class QueryRouter:
    """Routes queries to appropriate tool chains."""
    
    # Patterns for current data (needs web_search + web_fetch)
    CURRENT_DATA_PATTERNS = [
        r'погод[аеуы]',
        r'температур[аеуы]',
        r'курс[аеуы]?\s+(доллар|евро|рубл)',
        r'новост[аиеуы]',
        r'что\s+сегодня',
        r'что\s+произошл',
        r'актуальн',
        r'сегодня',
        r'завтра',
        r'прогноз',
        r'онлайн',
        r'tomorrow',
        r'today',
        r'weather',
        r'forecast',
        r'news',
        r'current',
    ]
    
    # Patterns for knowledge (can be answered directly)
    KNOWLEDGE_PATTERNS = [
        r'что\s+(такое|означает|представляет)',
        r'объясни[йте]?',
        r'расскажи[йте]?\s+(о|про|об)',
        r'как\s+(работает|устроен|создан)',
        r'почему',
        r'зачем',
        r'в\s+чем\s+(разница|смысл)',
        r'что\s+знаешь\s+о',
        r'define',
        r'what\s+is',
        r'explain',
        r'how\s+does',
        r'why',
    ]
    
    # Patterns for code
    CODE_PATTERNS = [
        r'напиши\s+(код|скрипт|программу|функцию|класс)',
        r'создай\s+(скрипт|программу|файл)',
        r'исправь\s+(код|баг|ошибку)',
        r'допиши',
        r'рефакторинг',
        r'write\s+(code|script|function)',
        r'create\s+(script|program)',
        r'fix\s+(bug|error|code)',
    ]
    
    # Patterns for file operations
    FILE_OP_PATTERNS = [
        r'прочитай\s+(файл|код)',
        r'покажи\s+(содержимое|код|файл)',
        r'открой\s+файл',
        r'скачай\s+файл',
        r'read\s+(file|code)',
        r'show\s+(file|code)',
        r'download\s+file',
    ]
    
    def route(self, query: str) -> QueryType:
        """Determine query type."""
        query_lower = query.lower().strip()
        
        # Check current data first (most specific)
        if self._matches_patterns(query_lower, self.CURRENT_DATA_PATTERNS):
            return QueryType.CURRENT_DATA
        
        # Check file operations
        if self._matches_patterns(query_lower, self.FILE_OP_PATTERNS):
            return QueryType.FILE_OP
        
        # Check code requests
        if self._matches_patterns(query_lower, self.CODE_PATTERNS):
            return QueryType.CODE
        
        # Check knowledge questions
        if self._matches_patterns(query_lower, self.KNOWLEDGE_PATTERNS):
            return QueryType.KNOWLEDGE
        
        # Check for URLs (fetch them)
        if re.search(r'https?://', query_lower):
            return QueryType.FILE_OP
        
        # Check for search requests
        if any(w in query_lower for w in ['найди', 'найти', 'поищи', 'поиск', 'search', 'find']):
            return QueryType.SEARCH
        
        # Default: search if it looks like a question
        if any(w in query_lower for w in ['?', 'какой', 'какая', 'какое', 'где', 'когда', 'кто', 'что']):
            return QueryType.SEARCH
        
        return QueryType.CONVERSATION
    
    def _matches_patterns(self, text: str, patterns: list[str]) -> bool:
        """Check if text matches any pattern."""
        for pattern in patterns:
            if re.search(pattern, text):
                return True
        return False
    
    def get_tool_chain(self, query_type: QueryType) -> list[str]:
        """Get ordered list of tools to use for query type."""
        chains = {
            QueryType.CURRENT_DATA: ["web_search", "web_fetch"],
            QueryType.KNOWLEDGE: [],  # Direct answer
            QueryType.CODE: [],  # May need bash, write_file
            QueryType.FILE_OP: ["read_file", "web_fetch"],
            QueryType.SEARCH: ["web_search"],
            QueryType.CONVERSATION: [],  # Direct answer
        }
        return chains.get(query_type, [])
    
    def get_prompt_hint(self, query_type: QueryType) -> str:
        """Get hint for the LLM about how to handle this query."""
        hints = {
            QueryType.CURRENT_DATA: "Это запрос о текущих данных. Сначала НАЙДИ информацию через web_search, затем ПРОЧИТАЙ страницу через web_fetch и извлеки конкретные данные (числа, факты). Не показывай ссылки — покажи данные.",
            QueryType.KNOWLEDGE: "Это вопрос из области знаний. Ответь из своих знаний, кратко и по существу. Не ищи в интернете если знаешь ответ.",
            QueryType.CODE: "Это запрос на написание/изменение кода. Используй инструменты для создания файлов и выполнения команд.",
            QueryType.FILE_OP: "Это запрос на работу с файлами. Используй appropriate инструменты.",
            QueryType.SEARCH: "Найди информацию и кратко изложи ключевые факты.",
            QueryType.CONVERSATION: "Это разговорный запрос. Ответь дружелюбно и кратко.",
        }
        return hints.get(query_type, "")
