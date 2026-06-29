"""LLM provider management."""
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from enum import Enum


class ProviderType(Enum):
    OLLAMA = "ollama"
    OPENROUTER = "openrouter"
    HUGGINGFACE = "huggingface"
    OPENAI = "openai"
    CUSTOM = "custom"


@dataclass
class Provider:
    name: str
    type: ProviderType
    base_url: str
    api_key: str = ""
    models: list[str] = field(default_factory=list)
    default_model: str = ""
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "type": self.type.value,
            "base_url": self.base_url,
            "api_key": self.api_key,
            "models": self.models,
            "default_model": self.default_model
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "Provider":
        return cls(
            name=data["name"],
            type=ProviderType(data["type"]),
            base_url=data["base_url"],
            api_key=data.get("api_key", ""),
            models=data.get("models", []),
            default_model=data.get("default_model", "")
        )


# Pre-configured providers
PRESET_PROVIDERS = {
    "ollama": Provider(
        name="Ollama (Local)",
        type=ProviderType.OLLAMA,
        base_url="http://localhost:11434/v1",
        api_key="ollama",
        models=["qwen3:1.7b", "qwen3:4b", "qwen3:8b", "llama3:8b"],
        default_model="qwen3:1.7b"
    ),
    "openrouter": Provider(
        name="OpenRouter",
        type=ProviderType.OPENROUTER,
        base_url="https://openrouter.ai/api/v1",
        api_key="",
        models=[
            "openai/gpt-4o",
            "openai/gpt-4o-mini",
            "anthropic/claude-3.5-sonnet",
            "meta-llama/llama-3.1-8b-instruct",
            "qwen/qwen-2.5-7b-instruct",
            "google/gemini-2.0-flash-001",
        ],
        default_model="openai/gpt-4o-mini"
    ),
    "huggingface": Provider(
        name="HuggingFace Inference",
        type=ProviderType.HUGGINGFACE,
        base_url="https://router.huggingface.co/v1",
        api_key="",
        models=[
            "openai/gpt-oss-120b:fastest",
            "deepseek-ai/DeepSeek-R1:fastest",
            "meta-llama/Llama-3.3-70B-Instruct:fastest",
            "Qwen/Qwen2.5-72B-Instruct:fastest",
        ],
        default_model="openai/gpt-oss-120b:fastest"
    ),
    "openai": Provider(
        name="OpenAI",
        type=ProviderType.OPENAI,
        base_url="https://api.openai.com/v1",
        api_key="",
        models=["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        default_model="gpt-4o-mini"
    ),
}


class ProviderManager:
    """Manage LLM providers."""
    
    def __init__(self, config_dir: Optional[Path] = None):
        self.config_dir = config_dir or Path.home() / ".chip"
        self.config_dir.mkdir(parents=True, exist_ok=True)
        self.providers_file = self.config_dir / "providers.json"
        self.providers: dict[str, Provider] = {}
        self._load()
    
    def _load(self):
        """Load providers from file."""
        if self.providers_file.exists():
            try:
                with open(self.providers_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for key, pdata in data.items():
                    self.providers[key] = Provider.from_dict(pdata)
            except Exception:
                pass
        
        # Add preset providers if not exist
        for key, preset in PRESET_PROVIDERS.items():
            if key not in self.providers:
                self.providers[key] = preset
    
    def _save(self):
        """Save providers to file."""
        data = {key: p.to_dict() for key, p in self.providers.items()}
        with open(self.providers_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    
    def add_provider(self, key: str, provider: Provider):
        """Add a provider."""
        self.providers[key] = provider
        self._save()
    
    def remove_provider(self, key: str):
        """Remove a provider."""
        if key in self.providers:
            del self.providers[key]
            self._save()
    
    def get_provider(self, key: str) -> Optional[Provider]:
        """Get a provider by key."""
        return self.providers.get(key)
    
    def list_providers(self) -> list[tuple[str, Provider]]:
        """List all providers."""
        return list(self.providers.items())
    
    def get_all_models(self) -> list[tuple[str, str, str]]:
        """Get all models as (provider_key, model_name, display_name)."""
        models = []
        for key, provider in self.providers.items():
            for model in provider.models:
                display = f"{provider.name}: {model}"
                models.append((key, model, display))
        return models
