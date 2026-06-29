"""Provider API client for listing models."""
import requests
from typing import Optional
from dataclasses import dataclass


@dataclass
class ModelInfo:
    id: str
    name: str
    provider: str
    size: str = ""
    
    def __str__(self):
        if self.size:
            return f"{self.name} ({self.size})"
        return self.name


def fetch_models_openrouter(api_key: str) -> list[ModelInfo]:
    """Fetch models from OpenRouter."""
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        response = requests.get(
            "https://openrouter.ai/api/v1/models",
            headers=headers,
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            models = []
            for m in data.get("data", []):
                model_id = m.get("id", "")
                name = m.get("name", model_id)
                pricing = m.get("pricing", {})
                prompt_price = float(pricing.get("prompt", "0"))
                if prompt_price == 0:
                    size = "free"
                else:
                    size = f"${prompt_price*1000000:.2f}/M tokens"
                models.append(ModelInfo(id=model_id, name=name, provider="openrouter", size=size))
            return models[:50]  # Limit to 50
    except Exception:
        pass
    return []


def fetch_models_huggingface(api_key: str) -> list[ModelInfo]:
    """Fetch models from HuggingFace Inference API."""
    try:
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        response = requests.get(
            "https://huggingface.co/api/models?pipeline_tag=text-generation&sort=downloads&limit=50",
            headers=headers,
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            models = []
            for m in data:
                model_id = m.get("id", "")
                models.append(ModelInfo(id=model_id, name=model_id, provider="huggingface"))
            return models
    except Exception:
        pass
    return []


def fetch_models_openai(api_key: str) -> list[ModelInfo]:
    """Fetch models from OpenAI."""
    try:
        headers = {"Authorization": f"Bearer {api_key}"}
        response = requests.get(
            "https://api.openai.com/v1/models",
            headers=headers,
            timeout=15
        )
        if response.status_code == 200:
            data = response.json()
            models = []
            for m in data.get("data", []):
                model_id = m.get("id", "")
                models.append(ModelInfo(id=model_id, name=model_id, provider="openai"))
            return models
    except Exception:
        pass
    return []


def fetch_models_ollama() -> list[ModelInfo]:
    """Fetch installed Ollama models."""
    try:
        import subprocess
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            models = []
            lines = result.stdout.strip().split("\n")[1:]
            for line in lines:
                parts = line.split()
                if parts:
                    name = parts[0]
                    size = parts[2] if len(parts) > 2 else ""
                    models.append(ModelInfo(id=name, name=name, provider="ollama", size=size))
            return models
    except Exception:
        pass
    return []


def fetch_models(provider: str, api_key: str = "") -> list[ModelInfo]:
    """Fetch models from specified provider."""
    if provider == "ollama":
        return fetch_models_ollama()
    elif provider == "openrouter":
        return fetch_models_openrouter(api_key)
    elif provider == "huggingface":
        return fetch_models_huggingface(api_key)
    elif provider == "openai":
        return fetch_models_openai(api_key)
    return []
