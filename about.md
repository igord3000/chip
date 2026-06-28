# About Chip Agent

## Описание

**Chip** — AI coding-агент с GUI интерфейсом, кэшированием и модульной архитектурой.

Работает локально через Ollama с моделями qwen3.

## Возможности

- **Textual GUI** — современный интерфейс в терминале
- **CLI чат** — классический режим
- **Кэширование** — экономия токенов (ResponseCache + SemanticCache)
- **Память** — долгосрочная память между сессиями
- **Инструменты** — bash, файлы, интернет, субагенты
- **Отслеживание контекста** — визуальный индикатор токенов

## Установка

```bash
git clone https://github.com/igord3000/chip.git
cd chip
pip install -e .
chip -s
```

## Использование

```bash
chip                          # GUI
chip -c                       # CLI чат
chip -c "задача"              # CLI с задачей
chip -m qwen3:8b              # Указать модель
chip --status                 # Статус
```

## Архитектура

```
chip/
├── chip/
│   ├── cache.py           # Кэширование
│   ├── memory.py          # Долгосрочная память
│   ├── agent.py           # Оркестратор
│   ├── llm.py             # LLM клиент
│   ├── config.py          # Конфигурация
│   ├── tools/             # Инструменты
│   └── ui/
│       └── textual_app.py # GUI
└── pyproject.toml
```

## Видеокарта

Рекомендуется NVIDIA с 6+ GB VRAM:
- RTX 3050 6GB — qwen3:8b
- RTX 3060 12GB — qwen3:14b
- RTX 3070+ — qwen3:32b

## Ссылки

- GitHub: https://github.com/igord3000/chip
- Ollama: https://ollama.ai
- Textual: https://textual.textualize.io
