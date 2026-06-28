# Chip Agent

Minimal coding agent with context tracking and checkpoint system.

## Features

- **Modular architecture** — easy to add new tools
- **Context tracking** — visual token usage indicator
- **Auto checkpoints** — save session when approaching limit
- **CLI with Rich** — beautiful terminal interface
- **Multiple tools** — bash, read_file, write_file, list_files

## Installation

```bash
# Clone repository
git clone https://github.com/alexey-goloburdin/chip
cd chip

# Install dependencies
uv sync

# Or via pip
pip install -e .
```

## Configuration

Set via environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `LLM_BASE_URL` | LLM server URL | `http://localhost:11434/v1` |
| `LLM_API_KEY` | API key | `ollama` |
| `LLM_MODEL` | Model name | `qwen3:8b` |
| `LLM_TEMPERATURE` | Temperature | `0.1` |
| `LLM_MAX_TOKENS` | Max response tokens | `4096` |
| `CONTEXT_MAX_TOKENS` | Max context size | `32000` |
| `CONTEXT_WARNING_THRESHOLD` | Warning threshold | `0.70` |
| `CONTEXT_CRITICAL_THRESHOLD` | Critical threshold | `0.90` |

## Usage

```bash
# Basic usage
chip "Write a Python script"

# With specific model
chip --model gpt-4 "Analyze this code"

# Resume session
chip --resume .chip/checkpoint_20240101_120000.json "Continue"
```

## Architecture

```
chip/
├── __init__.py        # Version
├── __main__.py        # Entry point
├── cli.py             # CLI interface
├── config.py          # Configuration
├── agent.py           # Main loop
├── llm.py             # LLM client
├── tools/
│   ├── base.py        # Base class
│   ├── bash.py        # Bash tool
│   ├── read_file.py   # File reading
│   ├── write_file.py  # File writing
│   └── list_files.py  # Directory listing
├── context/
│   ├── tracker.py     # Token counting
│   └── checkpoint.py  # Session saving
└── ui/
    └── terminal.py    # Rich interface
```

## Adding a New Tool

1. Create file `chip/tools/my_tool.py`
2. Inherit from `BaseTool`
3. Register in `chip/tools/__init__.py`

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
                "param": {"type": "string", "description": "Parameter description"}
            },
            "required": ["param"]
        }

    def execute(self, param: str = "") -> ToolResult:
        # Your implementation
        return ToolResult(success=True, output="Result")
```
