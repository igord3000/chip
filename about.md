# About Chip Agent

## Описание

**Chip** — минимальный coding-агент на Python с отслеживанием лимита контекста, системой чекпоинтов и поддержкой субагентов.

Агент общается с LLM через OpenAI-compatible API (Ollama, vLLM, LM Studio и др.) и выполняет задачи программирования с помощью инструментов.

### Возможности

- **Модульная архитектура** — легко добавлять новые инструменты
- **Отслеживание контекста** — визуальный индикатор использования токенов (tiktoken)
- **Автоматические чекпоинты** — сохранение сессии при подходе к лимиту контекста
- **Субагенты** — параллельное выполнение подзадач
- **CLI с Rich** — красивый интерфейс в терминале
- **5 встроенных инструментов** — bash, read_file, write_file, list_files, subagent
- **Единая команда установки** — `chip setup` настроит всё автоматически

### Поддерживаемые LLM

| Провайдер | URL по умолчанию |
|-----------|------------------|
| Ollama | http://localhost:11434/v1 |
| vLLM | http://localhost:8000/v1 |
| LM Studio | http://localhost:1234/v1 |
| OpenAI | https://api.openai.com/v1 |
| Together AI | https://api.together.xyz/v1 |

---

## Структура проекта

```
chip/
├── chip/                        # Основной пакет
│   ├── __init__.py              # Версия пакета
│   ├── __main__.py              # Точка входа (python -m chip)
│   ├── cli.py                   # CLI команды (setup, run, status, sessions)
│   ├── config.py                # Конфигурация из env-переменных
│   ├── agent.py                 # Основной цикл агента
│   ├── llm.py                   # LLM клиент с обработкой ошибок
│   ├── subagent.py              # Система субагентов
│   │
│   ├── tools/                   # Инструменты
│   │   ├── __init__.py          # Реестр инструментов
│   │   ├── base.py              # Базовый класс BaseTool
│   │   ├── bash.py              # Выполнение shell-команд
│   │   ├── read_file.py         # Чтение файлов
│   │   ├── write_file.py        # Запись файлов
│   │   ├── list_files.py        # Список файлов
│   │   └── subagent.py          # Инструмент запуска субагентов
│   │
│   ├── context/                 # Управление контекстом
│   │   ├── __init__.py
│   │   ├── tracker.py           # Подсчёт токенов (tiktoken)
│   │   └── checkpoint.py        # Сохранение/восстановление сессий
│   │
│   └── ui/                      # Пользовательский интерфейс
│       ├── __init__.py
│       └── terminal.py          # Rich-интерфейс для терминала
│
├── pyproject.toml               # Метаданные пакета
├── .python-version              # Версия Python (3.12)
├── .env.example                 # Пример конфигурации
├── .gitignore                   # Игнорируемые файлы
├── LICENSE                      # MIT лицензия
├── README.md                    # Документация (рус.)
├── README_EN.md                 # Документация (англ.)
└── about.md                     # Этот файл
```

---

## История изменений

### v0.2.0 — 2025-06-28

**Модульная архитектура + субагенты**

- Полная переработка кода из одного файла в модульную структуру
- Добавлен `cli.py` с командами: `setup`, `run`, `status`, `sessions`
- Добавлен `config.py` — конфигурация через env-переменные
- Добавлен `llm.py` — LLM клиент с обработкой ошибок и retry
- Добавлен `subagent.py` — система параллельных субагентов
- Добавлен `tracker.py` — подсчёт токенов через tiktoken
- Добавлен `checkpoint.py` — автоматическое сохранение сессий
- Добавлен `terminal.py` — Rich-интерфейс с цветным выводом
- Инструменты вынесены в отдельный модуль `tools/`
- Добавлен `SubagentTool` для запуска подзадач из агента
- Автоматическое сохранение при превышении лимита контекста
- CLI: `chip setup` — автоматическая установка Ollama и модели
- CLI: `chip run "задача"` — запуск задачи
- CLI: `chip status` — проверка статуса системы
- CLI: `chip sessions list|show|clean` — управление сессиями

### v0.1.0 — 2025-06-28

**Первая версия**

- Минимальный coding-агент в одном файле `chebupelka.py`
- Один инструмент: `bash`
- Цикл взаимодействия с LLM
- OpenAI-compatible API
- Зависимость только от `requests`

---

## Команды CLI

| Команда | Описание |
|---------|----------|
| `chip setup` | Автоматическая настройка (Ollama + модель) |
| `chip setup --model qwen3:14b` | Настройка с конкретной моделью |
| `chip run "задача"` | Запуск задачи |
| `chip run --model gpt-4 "задача"` | Запуск с другой моделью |
| `chip run --resume checkpoint.json "продолжай"` | Продолжение сессии |
| `chip status` | Статус Ollama и конфигурации |
| `chip sessions list` | Список сохранённых сессий |
| `chip sessions show <id>` | Просмотр сессии |
| `chip sessions clean` | Очистка всех сессий |

---

## Инструменты

| Инструмент | Описание | Параметры |
|------------|----------|-----------|
| `bash` | Выполнение команд | `command` |
| `read_file` | Чтение файлов | `path`, `offset`, `limit` |
| `write_file` | Запись файлов | `path`, `content`, `append` |
| `list_files` | Список файлов | `path`, `pattern`, `recursive` |
| `subagent` | Запуск субагента | `prompt`, `parallel` |

---

## Конфигурация

Переменные окружения (`.env`):

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
CHECKPOINT_DIR=.chebupelka
```

---

## Лицензия

MIT License — свободное использование, модификация и распространение.
