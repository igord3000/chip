"""Settings screen for Chip agent."""
import subprocess
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Label, Button, Input, RadioButton, RadioSet
from textual.binding import Binding
from textual import on

from chip.config import load_config, AgentConfig


class SettingsScreen(Static):
    """Settings panel."""
    
    def __init__(self, config: AgentConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self._installed_models = self._get_installed_models()
    
    def _get_installed_models(self) -> list[str]:
        """Get list of installed Ollama models."""
        try:
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
    
    def compose(self) -> ComposeResult:
        with Vertical(id="settings-panel"):
            yield Label("[bold]Настройки[/bold]", id="settings-title")
            
            # Current model
            yield Label(f"Текущая модель: [bold]{self.config.llm.model}[/bold]", id="current-model")
            
            # Available models
            yield Label("\nУстановленные модели:", classes="section-header")
            
            models = self._installed_models
            if models:
                for model in models:
                    size = self._get_model_size(model)
                    yield RadioButton(f"{model} ({size})", id=f"model_{model.replace(':', '_')}")
            else:
                yield Label("[dim]Нет установленных моделей[/dim]")
            
            # Download new model
            yield Label("\nСкачать новую модель:", classes="section-header")
            with Horizontal():
                yield Input(placeholder="qwen3:8b", id="new-model-input")
                yield Button("Скачать", id="download-btn", variant="primary")
            
            # Cache
            yield Label("\nКэш:", classes="section-header")
            cache_dir = Path.home() / ".chip" / "cache"
            cache_count = len(list(cache_dir.glob("*.json"))) if cache_dir.exists() else 0
            yield Label(f"Записей в кэше: {cache_count}")
            yield Button("Очистить кэш", id="clear-cache-btn", variant="warning")
    
    def _get_model_size(self, model: str) -> str:
        """Get model size from Ollama."""
        try:
            result = subprocess.run(
                ["ollama", "show", model],
                capture_output=True, text=True, timeout=5
            )
            if result.returncode == 0:
                for line in result.stdout.split("\n"):
                    if "size" in line.lower():
                        return line.split(":")[-1].strip()
        except Exception:
            pass
        return "?"
    
    @on(Button.Pressed, "#download-btn")
    async def handle_download(self):
        """Download a new model."""
        input_widget = self.query_one("#new-model-input")
        model_name = input_widget.value.strip()
        
        if not model_name:
            return
        
        self.query_one("#current-model").update(f"Скачивание {model_name}...")
        
        try:
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                self.query_one("#current-model").update(f"[green]✓ {model_name} скачана[/green]")
                self._installed_models = self._get_installed_models()
            else:
                self.query_one("#current-model").update(f"[red]✗ Ошибка: {result.stderr[:100]}[/red]")
        except Exception as e:
            self.query_one("#current-model").update(f"[red]✗ Ошибка: {e}[/red]")
    
    @on(Button.Pressed, "#clear-cache-btn")
    async def handle_clear_cache(self):
        """Clear cache."""
        cache_dir = Path.home() / ".chip" / "cache"
        if cache_dir.exists():
            for f in cache_dir.glob("*.json"):
                f.unlink()
            self.query_one("#current-model").update("[green]Кэш очищен[/green]")
    
    @on(RadioButton.Changed)
    def handle_model_select(self, event: RadioButton.Changed):
        """Handle model selection."""
        if event.radio_button.value:
            model_name = event.radio_button.id.replace("model_", "").replace("_", ":")
            self.config.llm.model = model_name
            self.query_one("#current-model").update(f"Текущая модель: [bold]{model_name}[/bold]")
            
            # Save to config file
            config_path = Path.home() / ".chip" / "config.json"
            config_path.parent.mkdir(parents=True, exist_ok=True)
            import json
            with open(config_path, "w") as f:
                json.dump({"model": model_name}, f)
