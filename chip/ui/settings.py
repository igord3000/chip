"""Settings screen for Chip agent."""
import json
import subprocess
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.widgets import Static, Label, Button, Input, Select, Checkbox
from textual import on

from chip.config import load_config, AgentConfig
from chip.providers import ProviderManager
from chip.provider_api import fetch_models, ModelInfo


class SettingsScreen(Static):
    """Settings panel with scrolling."""
    
    def __init__(self, config: AgentConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.provider_manager = ProviderManager()
        self._current_provider = "ollama"
    
    def compose(self) -> ComposeResult:
        # Determine current provider from base_url
        current_provider = "ollama"
        for key, p in self.provider_manager.list_providers():
            if p.base_url == self.config.llm.base_url:
                current_provider = key
                break
        
        with ScrollableContainer(id="settings-scroll"):
            # Current model
            yield Label(f"Текущая модель: [bold]{self.config.llm.model}[/bold]", id="current-model")
            
            # Provider
            yield Label("Провайдер:", classes="section")
            provider_options = [(f"{p.name}", key) for key, p in self.provider_manager.list_providers()]
            yield Select(provider_options, id="provider-select", prompt="Выберите провайдер", value=current_provider)
            
            # API Key - show if exists
            provider = self.provider_manager.get_provider(current_provider)
            key_hint = f"{'*' * 8}...{provider.api_key[-4:]}" if provider and provider.api_key else ""
            yield Label("API ключ:", classes="section")
            yield Input(placeholder=key_hint or "Введите API ключ...", id="api-key-input", password=True)
            with Horizontal():
                yield Button("Проверить", id="validate-key-btn")
                yield Button("Сохранить ключ", id="save-key-btn")
            yield Label("", id="key-status")
            
            # Models
            yield Label("Модели:", classes="section")
            with Horizontal():
                yield Button("Загрузить", id="load-models-btn")
                yield Checkbox("Только бесплатные", id="free-only-checkbox", value=True)
            yield Select([], id="model-select", prompt="Нажмите 'Загрузить'")
            yield Label("", id="model-status")
            
            # Max tokens
            yield Label("Макс. токенов:", classes="section")
            yield Input(value=str(self.config.llm.max_tokens), id="max-tokens-input")
            
            # Actions
            yield Button("Применить", id="apply-btn", variant="success")
    
    @on(Select.Changed, "#provider-select")
    def handle_provider_change(self, event: Select.Changed):
        provider_key = event.value
        if provider_key:
            self._current_provider = provider_key
            provider = self.provider_manager.get_provider(provider_key)
            if provider:
                self.config.llm.base_url = provider.base_url
    
    @on(Select.Changed, "#model-select")
    def handle_model_change(self, event: Select.Changed):
        model = event.value
        if model:
            self.config.llm.model = model
            self.query_one("#current-model").update(f"Текущая модель: [bold]{model}[/bold]")
            self._save_config()
    
    @on(Button.Pressed, "#load-models-btn")
    def handle_load_models(self):
        self.query_one("#model-status").update("[yellow]Загрузка...[/yellow]")
        
        provider = self.provider_manager.get_provider(self._current_provider)
        if not provider:
            self.query_one("#model-status").update("[red]Выберите провайдер[/red]")
            return
        
        models = fetch_models(self._current_provider, provider.api_key)
        
        free_only = self.query_one("#free-only-checkbox").value
        if free_only:
            models = [m for m in models if ":free" in m.id or m.size == "free"]
        
        if models:
            select = self.query_one("#model-select")
            options = [(f"{m.name} ({m.size})" if m.size else m.name, m.id) for m in models]
            select.set_options(options)
            self.query_one("#model-status").update(f"[green]Загружено {len(models)} моделей[/green]")
        else:
            self.query_one("#model-status").update("[red]Не удалось загрузить[/red]")
    
    @on(Button.Pressed, "#validate-key-btn")
    def handle_validate_key(self):
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
            self.query_one("#key-status").update(f"[green]✓ {message}[/green]" if is_valid else f"[red]✗ {message}[/red]")
        except Exception as e:
            self.query_one("#key-status").update(f"[red]✗ {e}[/red]")
    
    @on(Button.Pressed, "#save-key-btn")
    def handle_save_key(self):
        key_input = self.query_one("#api-key-input")
        api_key = key_input.value.strip()
        
        if not api_key:
            self.query_one("#key-status").update("[red]Введите ключ[/red]")
            return
        
        provider = self.provider_manager.get_provider(self._current_provider)
        if provider:
            provider.api_key = api_key
            self.provider_manager._save()
            self.config.llm.api_key = api_key
            self.query_one("#key-status").update("[green]✓ Сохранено[/green]")
    
    @on(Button.Pressed, "#apply-btn")
    def handle_apply(self):
        # Update max_tokens
        try:
            self.config.llm.max_tokens = int(self.query_one("#max-tokens-input").value)
        except ValueError:
            pass
        
        self._save_config()
        self.query_one("#model-status").update("[green]✓ Применено[/green]")
    
    def _save_config(self):
        config_path = Path.home() / ".chip" / "config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(config_path, "w") as f:
            json.dump({
                "model": self.config.llm.model,
                "base_url": self.config.llm.base_url,
                "api_key": self.config.llm.api_key,
                "max_tokens": self.config.llm.max_tokens,
            }, f)
