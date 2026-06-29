"""Configuration management with env vars and config file support."""
import os
import json
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


def _detect_model() -> str:
    """Auto-detect available Ollama model."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]  # Skip header
            for line in lines:
                model_name = line.split()[0]
                if "qwen" in model_name:
                    return model_name
            if lines:
                return lines[0].split()[0]
    except Exception:
        pass
    return "qwen3:1.7b"


def _load_saved_config() -> dict:
    """Load saved config from file."""
    config_path = Path.home() / ".chip" / "config.json"
    if config_path.exists():
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}


@dataclass
class LLMConfig:
    base_url: str = field(default_factory=lambda: os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"))
    api_key: str = field(default_factory=lambda: os.getenv("LLM_API_KEY", "ollama"))
    model: str = field(default_factory=lambda: os.getenv("LLM_MODEL") or _detect_model())
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
    
    # Load saved settings
    saved = _load_saved_config()
    if saved:
        if "model" in saved:
            config.llm.model = saved["model"]
        if "base_url" in saved:
            config.llm.base_url = saved["base_url"]
        if "api_key" in saved:
            config.llm.api_key = saved["api_key"]
    
    return config
