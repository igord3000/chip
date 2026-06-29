# Chip Agent 2.0 — Universal Orchestrator

## Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                      USER INTERFACE                             │
│                 (Textual GUI / CLI / API)                       │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                   ORCHESTRATOR CORE                             │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Intent Router & Context Manager                        │   │
│  │  • Определяет тип задачи                                │   │
│  │  • Управляет историей диалога                           │   │
│  │  • Планирует цепочки действий (Plan & Execute)          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Tool Registry (реестр всех инструментов)              │   │
│  │  • Динамическая регистрация                            │   │
│  │  • Описание в JSON Schema                              │   │
│  │  • Права доступа и стоимость вызовов                   │   │
│  └─────────────────────────────────────────────────────────┘   │
│                            │                                    │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Execution Engine (движок выполнения)                  │   │
│  │  • Выполняет цепочки инструментов                      │   │
│  │  • Параллельное выполнение                             │   │
│  │  • Retry и fallback механизмы                          │   │
│  │  • Кэширование результатов                             │   │
│  └─────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    TOOL LAYER (инструменты)                     │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │  DATA TOOLS  │ │  CREATIVE    │ │  MEDIA TOOLS │           │
│  │ • Web Search │ │ • Image Gen  │ │ • Video Gen  │           │
│  │ • Web Fetch  │ │ • Music Gen  │ │ • Audio Edit │           │
│  │ • DB Query   │ │ • PPT Maker  │ │ • Screen Rec │           │
│  │ • File Ops   │ │ • Chart Plot │ │ • Stream     │           │
│  │ • API Calls  │ │ • Design     │ │ • Transcode  │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│                                                                  │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │   CODE TOOLS │ │  INTEGRATION │ │  SYSTEM      │           │
│  │ • Bash       │ │ • Email      │ │ • Calculator │           │
│  │ • Git        │ │ • Slack      │ │ • Date/Time  │           │
│  │ • Lint       │ │ • Jira       │ │ • Math       │           │
│  │ • Test       │ │ • Google Cal │ │ • Translate  │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

## Ключевые компоненты

### 1. Tool Registry — динамический реестр инструментов

```python
# chip/tool_registry.py

class ToolCategory(Enum):
    DATA = "data"
    CREATIVE = "creative"
    MEDIA = "media"
    CODE = "code"
    INTEGRATION = "integration"
    SYSTEM = "system"

@dataclass
class ToolMetadata:
    name: str
    description: str
    category: ToolCategory
    schema: Dict[str, Any]
    cost: int = 1
    requires_auth: bool = False
    timeout: int = 30
    cache_ttl: int = 0
    parallelizable: bool = False

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Any] = {}
        self._metadata: Dict[str, ToolMetadata] = {}
    
    def register(self, tool_class, metadata: ToolMetadata):
        self._tools[metadata.name] = tool_class
        self._metadata[metadata.name] = metadata
    
    def get_schemas_for_llm(self) -> List[Dict]:
        schemas = []
        for name, meta in self._metadata.items():
            schemas.append({
                "type": "function",
                "function": {
                    "name": meta.name,
                    "description": meta.description,
                    "parameters": meta.schema,
                }
            })
        return schemas
    
    def load_from_module(self, module_path: str):
        """Динамическая загрузка инструментов"""
        import pkgutil
        import chip.tools
        for module_info in pkgutil.iter_modules(chip.tools.__path__):
            module = importlib.import_module(f'chip.tools.{module_info.name}')
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if inspect.isclass(attr) and issubclass(attr, BaseTool):
                    # Регистрируем автоматически
                    pass
```

### 2. Plan & Execute — планирование цепочек

```python
# chip/planner.py

@dataclass
class Task:
    tool: str
    parameters: Dict[str, Any]
    depends_on: List[str]
    status: str = "pending"
    result: Optional[Any] = None

class Planner:
    def __init__(self, llm_client):
        self.llm = llm_client
    
    def create_plan(self, query: str) -> List[Task]:
        """LLM разбивает запрос на подзадачи"""
        prompt = f"""
        Разбей запрос на простые подзадачи.
        Запрос: {query}
        Ответ: список задач, по одной на строку.
        """
        # Вызываем LLM для декомпозиции
        # Возвращаем список Task
        pass

class PlanExecutor:
    def execute(self, plan: List[Task]) -> Dict[str, Any]:
        """Выполняет план с учетом зависимостей"""
        results = {}
        for task in plan:
            # Проверяем зависимости
            # Выполняем задачу
            # Сохраняем результат
            pass
        return results
```

### 3. Универсальный инструмент для API

```python
# chip/tools/universal_api.py

class UniversalAPITool(BaseTool):
    """Вызывает любой REST API"""
    
    name = "api_call"
    description = "Вызвать HTTP API"
    
    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                "headers": {"type": "object"},
                "body": {"type": "object"},
            },
            "required": ["url", "method"]
        }
    
    def execute(self, url, method="GET", headers=None, body=None):
        response = requests.request(method, url, headers=headers, json=body)
        return {"status": response.status_code, "data": response.json()}
```

## Таблица инструментов для расширения

| Категория | Инструмент | API | Сложность |
|-----------|-----------|-----|-----------|
| **Творчество** | | | |
| Генерация изображений | Stable Diffusion, DALL-E | API | Средняя |
| Генерация музыки | Suno AI, Riffusion | API | Высокая |
| Генерация видео | Runway, Pika | API | Высокая |
| **Офис** | | | |
| Презентации | Google Slides | API | Средняя |
| Таблицы | Google Sheets | API | Средняя |
| PDF | ReportLab | Библиотека | Низкая |
| **Визуализация** | | | |
| Графики | Matplotlib, Plotly | Библиотека | Низкая |
| Дашборды | Streamlit | Библиотека | Средняя |
| **Интеграции** | | | |
| Почта | Gmail | API | Низкая |
| Мессенджеры | Slack, Telegram | API | Низкая |
| **Система** | | | |
| Калькулятор | Встроенный | — | Низкая |
| Переводчик | Google Translate | API | Низкая |

## Ключевые принципы

1. **LLM отвечает за "Что"** — выбор инструмента и параметров
2. **Оркестратор отвечает за "Как"** — выполнение, ошибки, кэш
3. **Инструменты отвечают за "Сделать"** — реальные API вызовы
4. **Контекст связывает всё** — история, результаты, предпочтения

## Универсальный инструмент (шаблон)

```python
class UniversalAPITool(BaseTool):
    name = "api_call"
    description = "Вызвать любой HTTP API"
    
    def get_schema(self):
        return {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "DELETE"]},
                "headers": {"type": "object"},
                "body": {"type": "object"},
            },
            "required": ["url", "method"]
        }
    
    def execute(self, url, method="GET", headers=None, body=None):
        response = requests.request(method, url, headers=headers, json=body)
        return {"status": response.status_code, "data": response.json()}
```

## Дорожная карта

### Фаза 1: Базовый оркестратор (текущая)
- ✅ LLM выбирает инструменты
- ✅ Базовые инструменты
- ⬜ Сохранение контекста
- ⬜ Streaming

### Фаза 2: Планирование (1-2 недели)
- ⬜ Plan & Execute
- ⬜ Зависимости между задачами
- ⬜ Параллельное выполнение

### Фаза 3: Креативные инструменты (месяц)
- ⬜ Генерация изображений
- ⬜ Таблицы и графики
- ⬜ Презентации

### Фаза 4: Мультимедиа (2 месяца)
- ⬜ Генерация музыки
- ⬜ Генерация видео
- ⬜ Обработка медиа

### Фаза 5: Автоматизация (3 месяца)
- ⬜ Интеграция с сервисами
- ⬜ Автообнаружение API
- ⬜ MCP поддержка

## Вопросы по архитектуре

### Безопасность
- Уровни доверия для инструментов
- Подтверждение опасных операций
- Sandbox для кода

### Стоимость
- Кэширование платных запросов
- Fallback на бесплатные альтернативы
- Показ стоимости перед вызовом

### Ошибки
- Retry с экспоненциальной задержкой
- Fallback на другие инструменты
- Уведомление пользователя

### Производительность
- Асинхронное выполнение
- Прогресс-бары
- Фоновые задачи
