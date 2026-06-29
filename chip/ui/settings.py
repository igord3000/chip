"""Settings screen for Chip agent."""
import json
import subprocess
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Label, Button, Input, Select, LoadingIndicator
from textual.binding import Binding
from textual import on

from chip.config import load_config, AgentConfig
from chip.providers import ProviderManager
from chip.provider_api import fetch_models, ModelInfo


class SettingsScreen(Static):
    """Settings panel."""
    
    def __init__(self, config: AgentConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.provider_manager = ProviderManager()
        self._installed_models = self._get_installed_models()
        self._cloud_models: list[ModelInfo] = []
        self._current_provider = "ollama"
    
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
            
            # Current settings
            yield Label(
                f"Модель: [bold]{self.config.llm.model}[/bold] | "
                f"URL: [dim]{self.config.llm.base_url}[/dim]",
                id="current-settings"
            )
            
            # Provider selection
            yield Label("\nПровайдер:", classes="section-header")
            provider_options = [(f"{p.name}", key) for key, p in self.provider_manager.list_providers()]
            yield Select(provider_options, id="provider-select", prompt="Выберите провайдер")
            
            # API Key with buttons
            yield Label("API ключ:", classes="section-header")
            yield Input(placeholder="Введите API ключ...", id="api-key-input", password=True)
            with Horizontal(id="key-buttons"):
                yield Button("Проверить", id="validate-key-btn")
                yield Button("Сохранить", id="save-key-btn", variant="primary")
            yield Label("", id="key-status")
            
            # Model selection
            yield Label("Модель:", classes="section-header")
            yield Label("[dim]Нажмите 'Загрузить модели' для получения списка[/dim]", id="models-hint")
            
            # Model buttons
            with Horizontal(id="model-buttons"):
                yield Button("Загрузить модели", id="load-models-btn", variant="primary")
                yield Button("Проверить", id="test-model-btn")
            
            # Models dropdown (will be populated)
            yield Label("", id="models-label")
            yield Select([], id="model-select", prompt="Модели не загружены")
            
            yield Label("", id="model-status")
            
            # Download
            yield Label("\nСкачать модель (Ollama):", classes="section-header")
            with Horizontal():
                yield Input(placeholder="qwen3:8b", id="new-model-input")
                yield Button("Скачать", id="download-btn")
            
            # Cache
            yield Label("\nКэш:", classes="section-header")
            cache_dir = Path.home() / ".chip" / "cache"
            cache_count = len(list(cache_dir.glob("*.json"))) if cache_dir.exists() else 0
            yield Label(f"Записей: {cache_count}")
            yield Button("Очистить", id="clear-cache-btn")
    
    @on(Select.Changed, "#provider-select")
    def handle_provider_change(self, event: Select.Changed):
        """Handle provider selection."""
        provider_key = event.value
        if provider_key:
            self._current_provider = provider_key
            provider = self.provider_manager.get_provider(provider_key)
            if provider:
                self.config.llm.base_url = provider.base_url
                self._update_current_settings()
    
    @on(Button.Pressed, "#load-models-btn")
    def handle_load_models(self):
        """Load models from selected provider."""
        self.query_one("#models-label").update("[yellow]Загрузка моделей...[/yellow]")
        
        provider = self.provider_manager.get_provider(self._current_provider)
        if not provider:
            self.query_one("#models-label").update("[red]Выберите провайдер[/red]")
            return
        
        models = fetch_models(self._current_provider, provider.api_key)
        self._cloud_models = models
        
        if models:
            # Update the select widget
            select = self.query_one("#model-select")
            model_options = [(f"{m.name} ({m.size})" if m.size else m.name, m.id) for m in models]
            select.set_options(model_options)
            self.query_one("#models-label").update(f"[green]Загружено {len(models)} моделей[/green]")
        else:
            self.query_one("#models-label").update("[red]Не удалось загрузить модели[/red]")
    
    @on(Select.Changed, "#model-select")
    def handle_model_change(self, event: Select.Changed):
        """Handle model selection."""
        model = event.value
        if model:
            self.config.llm.model = model
            self._update_current_settings()
            self._save_config()
    
    @on(Button.Pressed, "#validate-key-btn")
    def handle_validate_key(self):
        """Validate API key."""
        self.query_one("#key-status").update("[yellow]Проверка...[/yellow]")
        
        provider = self.provider_manager.get_provider(self._current_provider)
        if not provider:
            self.query_one("#key-status").update("[red]Выберите провайдер[/red]")
            return
        
        key_input = self.query_one("#api-key-input")
        api_key = key_input.value.strip() or provider.api_key
        
        try:
            from chip.api_validator import validate_api_key
            is_valid, message = validate_api_key(self._current_provider, api_key, provider.base_url)
            if is_valid:
                self.query_one("#key-status").update(f"[green]✓ {message}[/green]")
            else:
                self.query_one("#key-status").update(f"[red]✗ {message}[/red]")
        except Exception as e:
            self.query_one("#key-status").update(f"[red]✗ {e}[/red]")
    
    @on(Button.Pressed, "#save-key-btn")
    def handle_save_key(self):
        """Save API key."""
        key_input = self.query_one("#api-key-input")
        api_key = key_input.value.strip()
        
        if not api_key:
            self.query_one("#key-status").update("[red]Введите API ключ[/red]")
            return
        
        provider = self.provider_manager.get_provider(self._current_provider)
        if provider:
            provider.api_key = api_key
            self.provider_manager._save()
            self.config.llm.api_key = api_key
            self._save_config()
            self.query_one("#key-status").update("[green]✓ Сохранено[/green]")
    
    @on(Button.Pressed, "#test-model-btn")
    def handle_test_model(self):
        """Test if model works."""
        self.query_one("#model-status").update("[yellow]Проверка...[/yellow]")
        
        provider = self.provider_manager.get_provider(self._current_provider)
        if not provider:
            self.query_one("#model-status").update("[red]Выберите провайдер[/red]")
            return
        
        try:
            from chip.api_validator import test_chat_completion
            is_valid, message = test_chat_completion(
                self._current_provider,
                provider.api_key,
                provider.base_url,
                self.config.llm.model
            )
            if is_valid:
                self.query_one("#model-status").update(f"[green]✓ {message}[/green]")
            else:
                self.query_one("#model-status").update(f"[red]✗ {message}[/red]")
        except Exception as e:
            self.query_one("#model-status").update(f"[red]✗ {e}[/red]")
    
    @on(Button.Pressed, "#download-btn")
    def handle_download(self):
        """Download a new model."""
        input_widget = self.query_one("#new-model-input")
        model_name = input_widget.value.strip()
        
        if not model_name:
            return
        
        self.query_one("#model-status").update(f"[yellow]Скачивание {model_name}...[/yellow]")
        
        try:
            result = subprocess.run(
                ["ollama", "pull", model_name],
                capture_output=True, text=True, timeout=300
            )
            if result.returncode == 0:
                self.query_one("#model-status").update(f"[green]✓ {model_name} скачана[/green]")
                self._installed_models = self._get_installed_models()
            else:
                self.query_one("#model-status").update(f"[red]✗ {result.stderr[:100]}[/red]")
        except Exception as e:
            self.query_one("#model-status").update(f"[red]✗ {e}[/red]")
    
    @on(Button.Pressed, "#clear-cache-btn")
    def handle_clear_cache(self):
        """Clear cache."""
        cache_dir = Path.home() / ".chip" / "cache"
        if cache_dir.exists():
            for f in cache_dir.glob("*.json"):
                f.unlink()
            self.query_one("#model-status").update("[green]Кэш очищен[/green]")
    
    def _update_current_settings(self):
        """Update current settings display."""
        self.query_one("#current-settings").update(
            f"Модель: [bold]{self.config.llm.model}[/bold] | "
            f"URL: [dim]{self.config.llm.base_url}[/dim]"
        )
    
    def _save_config(self):
        """Save config to file."""
        config_path = Path.home() / ".chip" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump({
                "model": self.config.llm.model,
                "base_url": self.config.llm.base_url,
                "api_key": self.config.llm.api_key,
            }, f)
