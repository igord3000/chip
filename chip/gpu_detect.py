"""Universal GPU detection and model recommendation."""
import subprocess
import platform
from dataclasses import dataclass
from typing import Optional


@dataclass
class GPUInfo:
    name: str
    vram_mb: int
    driver: str
    
    @property
    def vram_gb(self) -> float:
        return self.vram_mb / 1024
    
    @property
    def tier(self) -> str:
        if self.vram_mb >= 24000:
            return "high"
        elif self.vram_mb >= 12000:
            return "medium"
        elif self.vram_mb >= 6000:
            return "low"
        else:
            return "minimal"


def detect_gpu() -> Optional[GPUInfo]:
    """Detect GPU and VRAM."""
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            parts = result.stdout.strip().split(", ")
            if len(parts) >= 3:
                return GPUInfo(
                    name=parts[0].strip(),
                    vram_mb=int(parts[1].strip()),
                    driver=parts[2].strip()
                )
    except Exception:
        pass
    
    # Try alternative detection
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            vram = int(result.stdout.strip())
            return GPUInfo(name="Unknown GPU", vram_mb=vram, driver="unknown")
    except Exception:
        pass
    
    return None


def get_recommended_models(gpu: Optional[GPUInfo] = None) -> list[dict]:
    """Get recommended models based on GPU VRAM."""
    
    # All available models with VRAM requirements
    all_models = [
        # Small models (1-2 GB)
        {"name": "qwen3:0.6b", "size_gb": 0.5, "vram_needed": 1, "quality": "basic", "desc": "Минимальная, очень быстрая"},
        {"name": "qwen3:1.7b", "size_gb": 1.4, "vram_needed": 2, "quality": "basic", "desc": "Базовая, быстрая"},
        {"name": "qwen3-coder:1.5b", "size_gb": 1.0, "vram_needed": 2, "quality": "basic", "desc": "Для кода, базовая"},
        {"name": "deepseek-r1:1.5b", "size_gb": 1.0, "vram_needed": 2, "quality": "basic", "desc": "Рассуждения, базовая"},
        
        # Medium models (2-4 GB)
        {"name": "qwen3:4b", "size_gb": 2.5, "vram_needed": 4, "quality": "good", "desc": "Хорошее качество"},
        {"name": "gemma3:4b", "size_gb": 3.0, "vram_needed": 4, "quality": "good", "desc": "Google, хороший контекст"},
        {"name": "phi4-mini", "size_gb": 2.5, "vram_needed": 4, "quality": "good", "desc": "Microsoft, быстрая"},
        {"name": "llama3.2:3b", "size_gb": 2.0, "vram_needed": 3, "quality": "good", "desc": "Meta, хороший контекст"},
        {"name": "mistral:7b", "size_gb": 4.1, "vram_needed": 5, "quality": "high", "desc": "Хорошее качество"},
        
        # Large models (5-8 GB)
        {"name": "qwen3:8b", "size_gb": 5.0, "vram_needed": 6, "quality": "high", "desc": "Отличное качество"},
        {"name": "llama3.1:8b", "size_gb": 4.7, "vram_needed": 6, "quality": "high", "desc": "Meta, огромный контекст"},
        {"name": "gemma3:12b", "size_gb": 8.0, "vram_needed": 10, "quality": "high", "desc": "Google, огромный контекст"},
        
        # Extra large models (12+ GB)
        {"name": "qwen3:14b", "size_gb": 9.0, "vram_needed": 12, "quality": "ultra", "desc": "Отличное качество"},
        {"name": "llama3.1:70b", "size_gb": 40.0, "vram_needed": 48, "quality": "ultra", "desc": "Топовое качество"},
        
        # Specialized
        {"name": "qwen3-coder:7b", "size_gb": 4.5, "vram_needed": 6, "quality": "high", "desc": "Для кода"},
        {"name": "deepseek-r1:7b", "size_gb": 4.5, "vram_needed": 6, "quality": "high", "desc": "Рассуждения"},
    ]
    
    if gpu:
        # Filter by VRAM
        available = [m for m in all_models if m["vram_needed"] <= gpu.vram_gb * 0.9]
    else:
        # No GPU detected, show small models
        available = [m for m in all_models if m["vram_needed"] <= 4]
    
    return available


def get_model_categories() -> dict[str, list[str]]:
    """Get models grouped by category."""
    return {
        "Быстрые (1-3B)": ["qwen3:0.6b", "qwen3:1.7b", "llama3.2:3b", "phi4-mini"],
        "Средние (4-8B)": ["qwen3:4b", "gemma3:4b", "mistral:7b", "qwen3:8b"],
        "Крупные (12-70B)": ["qwen3:14b", "llama3.1:70b"],
        "Для кода": ["qwen3-coder:1.5b", "qwen3-coder:7b"],
        "Для рассуждений": ["deepseek-r1:1.5b", "deepseek-r1:7b"],
    }
