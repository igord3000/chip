"""Configuration management with env vars and config file support."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class LLMConfig:
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"))
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", "ollama"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL", "qwen3:8b"))
    temperature: float = field(default_factory=lambda: float(os.getenv("LLM_TEMPERATURE", "0.1")))
    max_tokens: int = field(default_factory=lambda: int(os.getenv("LLM_MAX_TOKENS", "4096")))
    timeout: int = field(default_factory=lambda: int(os.getenv("LLM_TIMEOUT", "120")))


@dataclass
class ContextConfig:
    max_context_tokens: int = field(default_factory=lambda: int(os.getenv("CONTEXT_MAX_TOKENS", "32000")))
    warning_threshold: float = field(default_factory=lambda: float(os.getenv("CONTEXT_WARNING_THRESHOLD", "0.70")))
    critical_threshold: float = field(default_factory=lambda: float(os.getenv("CONTEXT_CRITICAL_THRESHOLD", "0.90")))


@dataclass
class AgentConfig:
    max_turns: int = field(default_factory=lambda: int(os.getenv("AGENT_MAX_TURNS", "1000")))
    bash_timeout: int = field(default_factory=lambda: int(os.getenv("BASH_TIMEOUT", "120")))
    checkpoint_dir: Path = field(default_factory=lambda: Path(os.getenv("CHECKPOINT_DIR", Path.home() / ".chip")))

    llm: LLMConfig = field(default_factory=LLMConfig)
    context: ContextConfig = field(default_factory=ContextConfig)


def load_config() -> AgentConfig:
    config = AgentConfig()
    config.checkpoint_dir.mkdir(parents=True, exist_ok=True)
    return config
