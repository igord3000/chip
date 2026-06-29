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
from chip.provider_api import fetch_models
from chip.models_catalog import get_installed_models, get_models_for_vram, RECOMMENDED_MODELS


class SettingsScreen(Static):
    """Settings panel with scrolling."""
    
    def __init__(self, config: AgentConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.provider_manager = ProviderManager()
        self._current_provider = "ollama"
        self._installed_models = get_installed_models()
    
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
            
            # API Key
            provider = self.provider_manager.get_provider(current_provider)
            key_hint = f"{'*' * 8}...{provider.api_key[-4:]}" if provider and provider.api_key else ""
            yield Label("API ключ:", classes="section")
            yield Input(placeholder=key_hint or "Введите API ключ...", id="api-key-input", password=True)
            with Horizontal():
                yield Button("Проверить", id="validate-key-btn")
                yield Button("Сохранить ключ", id="save-key-btn")
            yield Label("", id="key-status")
            
            # Ollama Models
            yield Label("Локальные модели (Ollama):", classes="section")
            if self._installed_models:
                model_options = [(m, m) for m in self._installed_models]
                yield Select(model_options, id="model-select", prompt="Выберите модель")
            else:
                yield Label("[dim]Нет установленных моделей[/dim]")
            
            with Horizontal():
                yield Button("Обновить список", id="refresh-models-btn")
                yield Button("Проверить", id="test-model-btn")
            yield Label("", id="model-status")
            
            # Recommended models for download
            yield Label("Рекомендуемые модели (для 6GB VRAM):", classes="section")
            recommended = [m for m in RECOMMENDED_MODELS if m.fits_6gb]
            for model in recommended[:6]:
                installed = "✓" if model.name in self._installed_models else " "
                yield Label(f"  {installed} {model.display_name} — {model.description}")
            
            # Download new model
            yield Label("\nСкачать модель:", classes="section")
            with Horizontal():
                yield Input(placeholder="qwen3:4b", id="new-model-input")
                yield Button("Скачать", id="download-btn")
            
            # Cloud models
            yield Label("Облачные модели:", classes="section")
            cloud_models = [
                ("openai/gpt-4o-mini", "OpenAI GPT-4o Mini"),
                ("anthropic/claude-3.5-sonnet", "Claude 3.5 Sonnet"),
                ("meta-llama/llama-3.1-8b-instruct", "Llama 3.1 8B"),
                ("qwen/qwen-2.5-7b-instruct", "Qwen 2.5 7B"),
            ]
            yield Select([(d, m) for m, d in cloud_models], id="cloud-model-select", prompt="Облачная модель")
            
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
    
    @on(Select.Changed, "#cloud-model-select")
    def handle_cloud_model_change(self, event: Select.Changed):
        model = event.value
        if model:
            self.config.llm.model = model
            self.query_one("#current-model").update(f"Текущая модель: [bold]{model}[/bold]")
            self._save_config()
    
    @on(Button.Pressed, "#refresh-models-btn")
    def handle_refresh_models(self):
        """Refresh installed models list."""
        self._installed_models = get_installed_models()
        self.query_one("#model-status").update(f"[green]Обновлено: {len(self._installed_models)} моделей[/green]")
    
    @on(Button.Pressed, "#load-models-btn")
    def handle_load_models(self):
        self.query_one("#model-status").update("[yellow]Загрузка...[/yellow]")
        
        provider = self.provider_manager.get_provider(self._current_provider)
        if not provider:
            self.query_one("#model-status").update("[red]Выберите провайдер[/red]")
            return
        
        models = fetch_models(self._current_provider, provider.api_key)
        
        free_only = self.query_one("#free-only-checkbox").value if self.query_one("#free-only-checkbox") else True
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
    
    @on(Button.Pressed, "#test-model-btn")
    def handle_test_model(self):
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
            self.query_one("#model-status").update(f"[green]✓ {message}[/green]" if is_valid else f"[red]✗ {message}[/red]")
        except Exception as e:
            self.query_one("#model-status").update(f"[red]✗ {e}[/red]")
    
    @on(Button.Pressed, "#download-btn")
    def handle_download(self):
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
                self._installed_models = get_installed_models()
            else:
                self.query_one("#model-status").update(f"[red]✗ {result.stderr[:100]}[/red]")
        except Exception as e:
            self.query_one("#model-status").update(f"[red]✗ {e}[/red]")
    
    @on(Button.Pressed, "#apply-btn")
    def handle_apply(self):
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
