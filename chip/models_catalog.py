"""Ollama model catalog - recommended models for different VRAM sizes."""
from dataclasses import dataclass
from typing import Optional


@dataclass
class OllamaModel:
    name: str
    size_gb: float
    params: str
    context: int
    quality: str  # low, medium, high
    description: str
    
    @property
    def fits_6gb(self) -> bool:
        return self.size_gb <= 5.5  # Leave some VRAM for system
    
    @property
    def display_name(self) -> str:
        return f"{self.name} ({self.size_gb} GB, {self.params})"


# Recommended models for different VRAM sizes
RECOMMENDED_MODELS = [
    # For 6GB VRAM
    OllamaModel("qwen3:1.7b", 1.4, "1.7B", 40960, "low", "Быстрая, базовая"),
    OllamaModel("qwen3:4b", 2.5, "4B", 32768, "medium", "Хорошее качество"),
    OllamaModel("gemma3:4b", 3.0, "4B", 128000, "medium", "Google, большой контекст"),
    OllamaModel("phi4-mini", 2.5, "3.8B", 16384, "medium", "Microsoft, быстрая"),
    OllamaModel("llama3.2:3b", 2.0, "3B", 131072, "medium", "Meta, большой контекст"),
    OllamaModel("mistral:7b", 4.1, "7B", 32768, "high", "Mistral, хорошее качество"),
    
    # For 8GB+ VRAM
    OllamaModel("qwen3:8b", 5.0, "8B", 32768, "high", "Отличное качество"),
    OllamaModel("gemma3:12b", 8.0, "12B", 128000, "high", "Google, огромный контекст"),
    OllamaModel("llama3.1:8b", 4.7, "8B", 131072, "high", "Meta, огромный контекст"),
    
    # For 16GB+ VRAM
    OllamaModel("qwen3:14b", 9.0, "14B", 32768, "very_high", "Отличное качество"),
    OllamaModel("llama3.1:70b", 40.0, "70B", 131072, "very_high", "Meta, топовое качество"),
    
    # Special models
    OllamaModel("qwen3-coder:1.5b", 1.0, "1.5B", 32768, "low", "Для кода"),
    OllamaModel("qwen3-coder:7b", 4.5, "7B", 32768, "high", "Для кода, отличное"),
    OllamaModel("deepseek-r1:1.5b", 1.0, "1.5B", 32768, "low", "Рассуждения"),
]


def get_models_for_vram(vram_gb: float) -> list[OllamaModel]:
    """Get recommended models for given VRAM size."""
    return [m for m in RECOMMENDED_MODELS if m.size_gb <= vram_gb * 0.9]


def get_installed_models() -> list[str]:
    """Get list of installed Ollama models."""
    try:
        import subprocess
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            lines = result.stdout.strip().split("\n")[1:]
            return [line.split()[0] for line in lines if line.strip()]
    except Exception:
        pass
    return []


def get_model_info(model_name: str) -> Optional[dict]:
    """Get detailed info about a model."""
    try:
        import subprocess
        result = subprocess.run(
            ["ollama", "show", model_name],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            info = {}
            for line in result.stdout.split("\n"):
                if ":" in line:
                    key, _, value = line.partition(":")
                    info[key.strip()] = value.strip()
            return info
    except Exception:
        pass
    return None
