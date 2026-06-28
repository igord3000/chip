# Chip Agent

Минимальный coding-агент с отслеживанием лимита контекста, системой чекпоинтов и поддержкой субагентов.

## Быстрый старт (одной командой)

```bash
# Клонировать и запустить
git clone https://github.com/igord3000/chip && cd chip && pip install -e . && chip setup
```

## Установка

### Автоматическая установка

```bash
# Клонировать репозиторий
git clone https://github.com/igord3000/chip
cd chip

# Установить зависимости
pip install -e .

# Запустить настройку (установит Ollama и модель)
chip setup
```

### Ручная установка

```bash
# Установить Ollama
curl -fsSL https://ollama.ai/install.sh | sh

# Скачать модель
ollama pull qwen3:8b

# Установить Chip
pip install -e .
```

## Команды

### `chip setup` — Настройка

```bash
# Базовая настройка
chip setup

# С указанием модели
chip setup --model qwen3:14b

# Без установки Ollama (если уже установлен)
chip setup --skip-ollama
```

### `chip run` — Задачи

```bash
# Простая задача
chip run "Напиши hello world на Python"

# С указанием модели
chip run --model gpt-4 "Проанализируй код в main.py"

# Продолжение сессии
chip run --resume .chip/checkpoint_20240101_120000.json "Продолжай"

# Ограничение ходов
chip run --max-turns 10 "Создай веб-сервер"
```

### `chip status` — Статус

```bash
chip status
```

Вывод:
```
Chip Status
========================================
Ollama: Running

Available models:
  qwen3:8b    4.7 GB    2 hours ago
  llama3:8b   4.7 GB    3 days ago

.env: /path/to/project/.env
```

### `chip sessions` — Управление сессиями

```bash
# Список сессий
chip sessions list

# Просмотр сессии
chip sessions show checkpoint_20240101_120000.json

# Очистка
chip sessions clean
```

## Инструменты

### `bash` — Выполнение команд

```bash
# Агент автоматически использует bash для:
- Запуска скриптов
- Установки пакетов
- Компиляции кода
- Запуска тестов
```

Примеры использования агентом:
```python
# Установка пакета
bash("pip install requests")

# Запуск скрипта
bash("python main.py")

# Компиляция
bash("gcc -o program main.c")

# Тесты
bash("pytest tests/")
```

### `read_file` — Чтение файлов

```python
# Чтение всего файла
read_file(path="main.py")

# Чтение с.offset
read_file(path="main.py", offset=10, limit=50)
```

### `write_file` — Запись файлов

```python
# Создание файла
write_file(path="hello.py", content='print("Hello!")')

# Дозапись в файл
write_file(path="log.txt", content="New line\n", append=True)
```

### `list_files` — Список файлов

```python
# Текущая директория
list_files()

# Конкретная директория
list_files(path="src/")

# С паттерном
list_files(path="src/", pattern="*.py")

# Рекурсивно
list_files(path="src/", pattern="*.py", recursive=True)
```

### `subagent` — Субагенты

```python
# Запуск одной подзадачи
subagent(prompt="Напиши unit-тесты для функции calculate()")

# Параллельный запуск нескольких подзадач
subagent(prompt="
Напиши модуль auth.py
Напиши модуль database.py
Напиши модуль api.py
", parallel=True)
```

## Конфигурация

### Переменные окружения

Создайте файл `.env` в корне проекта:

```bash
# LLM
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL=qwen3:8b
LLM_TEMPERATURE=0.1
LLM_MAX_TOKENS=4096
LLM_TIMEOUT=120

# Контекст
CONTEXT_MAX_TOKENS=32000
CONTEXT_WARNING_THRESHOLD=0.70
CONTEXT_CRITICAL_THRESHOLD=0.90

# Агент
AGENT_MAX_TURNS=1000
BASH_TIMEOUT=120
CHECKPOINT_DIR=.chip
```

### Поддерживаемые LLM

| Провайдер | URL | Примеры моделей |
|-----------|-----|-----------------|
| Ollama | http://localhost:11434/v1 | qwen3, llama3, mistral |
| vLLM | http://localhost:8000/v1 | Любые модели |
| LM Studio | http://localhost:1234/v1 | Любые модели |
| OpenAI | https://api.openai.com/v1 | gpt-4, gpt-3.5-turbo |
| Together AI | https://api.together.xyz/v1 | mixtral, llama3 |
| Groq | https://api.groq.com/openai/v1 | mixtral, llama3 |

## Архитектура

```
chip/
├── __init__.py           # Версия
├── __main__.py           # Точка входа
├── cli.py                # CLI команды
├── config.py             # Конфигурация
├── agent.py              # Основной цикл агента
├── llm.py                # LLM клиент
├── subagent.py           # Система субагентов
├── tools/
│   ├── base.py           # Базовый класс инструментов
│   ├── bash.py           # Выполнение команд
│   ├── read_file.py      # Чтение файлов
│   ├── write_file.py     # Запись файлов
│   ├── list_files.py     # Список файлов
│   └── subagent.py       # Инструмент субагентов
├── context/
│   ├── tracker.py        # Подсчёт токенов
│   └── checkpoint.py     # Сохранение сессий
└── ui/
    └── terminal.py       # Rich интерфейс
```

## Добавление нового инструмента

1. Создайте файл `chip/tools/my_tool.py`:

```python
from .base import BaseTool, ToolResult

class MyTool(BaseTool):
    @property
    def name(self) -> str:
        return "my_tool"

    @property
    def description(self) -> str:
        return "Description of what tool does"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "param": {"type": "string", "description": "Parameter"}
            },
            "required": ["param"]
        }

    def execute(self, param: str = "") -> ToolResult:
        # Ваша реализация
        return ToolResult(success=True, output="Result")
```

2. Зарегистрируйте в `chip/tools/__init__.py`:

```python
from .my_tool import MyTool

# В _register_default_tools:
self.register(MyTool())
```

## Примеры использования

### Создание веб-приложения

```bash
chip run "Создай Flask API с CRUD операциями для пользователей"
```

Агент:
1. Создаст структуру проекта
2. Напишет код API
3. Добавит модели данных
4. Создаст тесты
5. Запустит сервер

### Анализ кода

```bash
chip run "Проанализируй код в src/ и найди баги"
```

Агент:
1. Прочитает все файлы в src/
2. Проанализирует код
3. Найдет потенциальные баги
4. Предложит исправления

### Написание тестов

```bash
chip run "Напиши unit-тесты для всех функций в utils.py"
```

Агент:
1. Прочитает utils.py
2. Поймет функции
3. Напишет тесты
4. Запустит и проверит

### Параллельная работа с субагентами

```bash
chip run "Разбей проект на модули: auth, database, api. Каждый модуль в отдельном файле."
```

Агент использовать субагенты для параллельной работы над модулями.

## Troubleshooting

### Ollama не запускается

```bash
# Проверить статус
ollama list

# Запустить вручную
ollama serve

# Проверить порт
curl http://localhost:11434/v1/models
```

### Модель не скачивается

```bash
# Проверить размер диска
df -h

# Скачать модель заново
ollama pull qwen3:8b
```

### Ошибка подключения

```bash
# Проверить URL в .env
cat .env | grep LLM_BASE_URL

# Проверить доступность сервера
curl $LLM_BASE_URL/v1/models
```

## Лицензия

MIT License
