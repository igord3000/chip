"""Settings screen for Chip agent."""
import json
import subprocess
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal
from textual.widgets import Static, Label, Button, Input, Select
from textual.binding import Binding
from textual import on

from chip.config import load_config, AgentConfig
from chip.providers import ProviderManager, PRESET_PROVIDERS


class SettingsScreen(Static):
    """Settings panel."""
    
    def __init__(self, config: AgentConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.provider_manager = ProviderManager()
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
            
            # Current settings display
            yield Label(
                f"Текущая модель: [bold]{self.config.llm.model}[/bold] | "
                f"URL: [dim]{self.config.llm.base_url}[/dim]",
                id="current-settings"
            )
            
            # Provider selection
            yield Label("\nПровайдер:", classes="section-header")
            provider_options = [(f"{p.name}", key) for key, p in self.provider_manager.list_providers()]
            yield Select(provider_options, id="provider-select", prompt="Выберите провайдер")
            
            # API Key
            yield Label("API ключ:", classes="section-header")
            with Horizontal():
                yield Input(placeholder="Введите API ключ...", id="api-key-input", password=True)
                yield Button("Проверить", id="validate-key-btn", variant="default")
                yield Button("Сохранить", id="save-key-btn", variant="primary")
            yield Label("", id="key-status")
            
            # Model selection for Ollama
            yield Label("\nЛокальные модели (Ollama):", classes="section-header")
            models = self._installed_models
            if models:
                model_options = [(m, m) for m in models]
                yield Select(model_options, id="model-select", prompt="Выберите модель")
            else:
                yield Label("[dim]Нет установленных моделей. Установите через: ollama pull <model>[/dim]")
            
            # Test model button
            with Horizontal():
                yield Button("Проверить модель", id="test-model-btn", variant="default")
            yield Label("", id="model-status")
            
            # Download new model
            yield Label("\nСкачать модель:", classes="section-header")
            with Horizontal():
                yield Input(placeholder="qwen3:8b", id="new-model-input")
                yield Button("Скачать", id="download-btn", variant="primary")
            
            # Cloud models
            yield Label("\nОблачные модели:", classes="section-header")
            cloud_models = [
                ("openai/gpt-4o-mini", "OpenAI GPT-4o Mini"),
                ("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet"),
                ("meta-llama/llama-3.1-8b-instruct", "Llama 3.1 8B"),
                ("qwen/qwen-2.5-7b-instruct", "Qwen 2.5 7B"),
            ]
            yield Select([(d, m) for m, d in cloud_models], id="cloud-model-select", prompt="Облачная модель")
            
            # Cache
            yield Label("\nКэш:", classes="section-header")
            cache_dir = Path.home() / ".chip" / "cache"
            cache_count = len(list(cache_dir.glob("*.json"))) if cache_dir.exists() else 0
            yield Label(f"Записей в кэше: {cache_count}")
            yield Button("Очистить кэш", id="clear-cache-btn", variant="warning")
    
    @on(Select.Changed, "#provider-select")
    def handle_provider_change(self, event: Select.Changed):
        """Handle provider selection."""
        provider_key = event.value
        if provider_key:
            provider = self.provider_manager.get_provider(provider_key)
            if provider:
                self.config.llm.base_url = provider.base_url
                self.config.llm.api_key = provider.api_key
                self.query_one("#current-settings").update(
                    f"Текущая модель: [bold]{self.config.llm.model}[/bold] | "
                    f"URL: [dim]{provider.base_url}[/dim]"
                )
    
    @on(Select.Changed, "#model-select")
    def handle_model_change(self, event: Select.Changed):
        """Handle model selection."""
        model = event.value
        if model:
            self.config.llm.model = model
            self._update_current_settings()
            self._save_config()
    
    @on(Select.Changed, "#cloud-model-select")
    def handle_cloud_model_change(self, event: Select.Changed):
        """Handle cloud model selection."""
        model = event.value
        if model:
            self.config.llm.model = model
            self._update_current_settings()
            self._save_config()
    
    @on(Button.Pressed, "#validate-key-btn")
    def handle_validate_key(self):
        """Validate API key."""
        from chip.api_validator import validate_api_key
        
        key_input = self.query_one("#api-key-input")
        api_key = key_input.value.strip()
        provider_select = self.query_one("#provider-select")
        provider_key = provider_select.value
        
        if not provider_key:
            self.query_one("#key-status").update("[red]Сначала выберите провайдер[/red]")
            return
        
        provider = self.provider_manager.get_provider(provider_key)
        if not provider:
            self.query_one("#key-status").update("[red]Провайдер не найден[/red]")
            return
        
        self.query_one("#key-status").update("[yellow]Проверка...[/yellow]")
        
        is_valid, message = validate_api_key(provider_key, api_key or provider.api_key, provider.base_url)
        
        if is_valid:
            self.query_one("#key-status").update(f"[green]✓ {message}[/green]")
        else:
            self.query_one("#key-status").update(f"[red]✗ {message}[/red]")
    
    @on(Button.Pressed, "#save-key-btn")
    def handle_save_key(self):
        """Save API key."""
        key_input = self.query_one("#api-key-input")
        api_key = key_input.value.strip()
        provider_select = self.query_one("#provider-select")
        provider_key = provider_select.value
        
        if not provider_key:
            self.query_one("#key-status").update("[red]Сначала выберите провайдер[/red]")
            return
        
        if api_key:
            provider = self.provider_manager.get_provider(provider_key)
            if provider:
                provider.api_key = api_key
                self.provider_manager._save()
                self.config.llm.api_key = api_key
                self.query_one("#key-status").update("[green]✓ API ключ сохранён[/green]")
    
    @on(Button.Pressed, "#test-model-btn")
    def handle_test_model(self):
        """Test if model works."""
        from chip.api_validator import test_chat_completion
        
        provider_select = self.query_one("#provider-select")
        provider_key = provider_select.value
        
        if not provider_key:
            self.query_one("#model-status").update("[red]Сначала выберите провайдер[/red]")
            return
        
        provider = self.provider_manager.get_provider(provider_key)
        if not provider:
            self.query_one("#model-status").update("[red]Провайдер не найден[/red]")
            return
        
        self.query_one("#model-status").update("[yellow]Проверка модели...[/yellow]")
        
        is_valid, message = test_chat_completion(
            provider_key,
            provider.api_key,
            provider.base_url,
            self.config.llm.model
        )
        
        if is_valid:
            self.query_one("#model-status").update(f"[green]✓ {message}[/green]")
        else:
            self.query_one("#model-status").update(f"[red]✗ {message}[/red]")
    
    @on(Button.Pressed, "#download-btn")
    async def handle_download(self):
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
                self.query_one("#model-status").update(f"[red]✗ Ошибка: {result.stderr[:100]}[/red]")
        except Exception as e:
            self.query_one("#model-status").update(f"[red]✗ Ошибка: {e}[/red]")
    
    @on(Button.Pressed, "#clear-cache-btn")
    async def handle_clear_cache(self):
        """Clear cache."""
        cache_dir = Path.home() / ".chip" / "cache"
        if cache_dir.exists():
            for f in cache_dir.glob("*.json"):
                f.unlink()
            self.query_one("#model-status").update("[green]Кэш очищен[/green]")
    
    def _update_current_settings(self):
        """Update current settings display."""
        self.query_one("#current-settings").update(
            f"Текущая модель: [bold]{self.config.llm.model}[/bold] | "
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
