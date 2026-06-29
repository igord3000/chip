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
from chip.gpu_detect import detect_gpu, get_recommended_models
from chip.models_catalog import get_installed_models


class SettingsScreen(Static):
    """Universal settings panel."""
    
    def __init__(self, config: AgentConfig, **kwargs):
        super().__init__(**kwargs)
        self.config = config
        self.provider_manager = ProviderManager()
        self.gpu = detect_gpu()
        self._installed_models = get_installed_models()
        self._current_provider = "ollama"
    
    def compose(self) -> ComposeResult:
        # Determine current provider
        for key, p in self.provider_manager.list_providers():
            if p.base_url == self.config.llm.base_url:
                self._current_provider = key
                break
        
        with ScrollableContainer(id="settings-scroll"):
            # GPU Info
            if self.gpu:
                yield Label(f"GPU: [bold]{self.gpu.name}[/bold] | VRAM: [bold]{self.gpu.vram_gb:.1f} GB[/bold]", id="gpu-info")
            else:
                yield Label("GPU: [dim]не обнаружен (CPU mode)[/dim]", id="gpu-info")
            
            # Current model
            yield Label(f"Текущая модель: [bold]{self.config.llm.model}[/bold]", id="current-model")
            
            # Provider
            yield Label("Провайдер:", classes="section")
            provider_options = [(f"{p.name}", key) for key, p in self.provider_manager.list_providers()]
            yield Select(provider_options, id="provider-select", prompt="Выберите провайдер", value=self._current_provider)
            
            # API Key
            provider = self.provider_manager.get_provider(self._current_provider)
            key_hint = f"{'*' * 8}...{provider.api_key[-4:]}" if provider and provider.api_key else ""
            yield Label("API ключ:", classes="section")
            yield Input(placeholder=key_hint or "Введите API ключ...", id="api-key-input", password=True)
            with Horizontal():
                yield Button("Проверить", id="validate-key-btn")
                yield Button("Сохранить", id="save-key-btn")
            yield Label("", id="key-status")
            
            # Local models (Ollama)
            yield Label("Локальные модели:", classes="section")
            if self._installed_models:
                model_options = [(m, m) for m in self._installed_models]
                yield Select(model_options, id="model-select", prompt="Выберите модель")
            else:
                yield Label("[dim]Нет моделей. Скачайте через 'Скачать'[/dim]")
            
            with Horizontal():
                yield Button("Обновить", id="refresh-btn")
                yield Button("Проверить", id="test-btn")
            yield Label("", id="model-status")
            
            # Recommended for download
            recommended = get_recommended_models(self.gpu)
            if recommended:
                yield Label("Рекомендуемые для скачивания:", classes="section")
                for m in recommended[:5]:
                    installed = "✓" if m["name"] in self._installed_models else " "
                    yield Label(f"  {installed} {m['name']} ({m['size_gb']} GB) — {m['desc']}")
            
            # Download
            yield Label("Скачать модель:", classes="section")
            with Horizontal():
                yield Input(placeholder="qwen3:4b", id="download-input")
                yield Button("Скачать", id="download-btn")
            yield Label("", id="download-status")
            
            # Cloud models
            yield Label("Облачные модели:", classes="section")
            cloud_models = [
                ("openai/gpt-4o-mini", "GPT-4o Mini (быстрая)"),
                ("anthropic/claude-3.5-sonnet", "Claude 3.5 (качественная)"),
                ("meta-llama/llama-3.1-8b-instruct", "Llama 3.1 8B"),
                ("qwen/qwen-2.5-7b-instruct", "Qwen 2.5 7B"),
                ("google/gemini-2.0-flash-001", "Gemini 2.0 Flash"),
            ]
            yield Select([(d, m) for m, d in cloud_models], id="cloud-select", prompt="Облачная модель")
            
            # Max tokens
            yield Label("Макс. токенов:", classes="section")
            yield Input(value=str(self.config.llm.max_tokens), id="max-tokens-input")
            
            # Apply
            yield Button("Применить", id="apply-btn", variant="success")
    
    @on(Select.Changed, "#provider-select")
    def handle_provider_change(self, event: Select.Changed):
        if event.value:
            self._current_provider = event.value
            provider = self.provider_manager.get_provider(event.value)
            if provider:
                self.config.llm.base_url = provider.base_url
    
    @on(Select.Changed, "#model-select")
    def handle_model_change(self, event: Select.Changed):
        if event.value:
            self.config.llm.model = event.value
            self.query_one("#current-model").update(f"Текущая модель: [bold]{event.value}[/bold]")
            self._save_config()
    
    @on(Select.Changed, "#cloud-select")
    def handle_cloud_change(self, event: Select.Changed):
        if event.value:
            self.config.llm.model = event.value
            self.query_one("#current-model").update(f"Текущая модель: [bold]{event.value}[/bold]")
            self._save_config()
    
    @on(Button.Pressed, "#refresh-btn")
    def handle_refresh(self):
        self._installed_models = get_installed_models()
        self.query_one("#model-status").update(f"[green]Обновлено: {len(self._installed_models)} моделей[/green]")
    
    @on(Button.Pressed, "#validate-key-btn")
    def handle_validate_key(self):
        self.query_one("#key-status").update("[yellow]Проверка...[/yellow]")
        provider = self.provider_manager.get_provider(self._current_provider)
        if not provider:
            self.query_one("#key-status").update("[red]Выберите провайдер[/red]")
            return
        api_key = self.query_one("#api-key-input").value.strip() or provider.api_key
        try:
            from chip.api_validator import validate_api_key
            is_valid, msg = validate_api_key(self._current_provider, api_key, provider.base_url)
            self.query_one("#key-status").update(f"[green]✓ {msg}[/green]" if is_valid else f"[red]✗ {msg}[/red]")
        except Exception as e:
            self.query_one("#key-status").update(f"[red]✗ {e}[/red]")
    
    @on(Button.Pressed, "#save-key-btn")
    def handle_save_key(self):
        api_key = self.query_one("#api-key-input").value.strip()
        if not api_key:
            self.query_one("#key-status").update("[red]Введите ключ[/red]")
            return
        provider = self.provider_manager.get_provider(self._current_provider)
        if provider:
            provider.api_key = api_key
            self.provider_manager._save()
            self.config.llm.api_key = api_key
            self.query_one("#key-status").update("[green]✓ Сохранено[/green]")
    
    @on(Button.Pressed, "#test-btn")
    def handle_test(self):
        self.query_one("#model-status").update("[yellow]Проверка...[/yellow]")
        provider = self.provider_manager.get_provider(self._current_provider)
        if not provider:
            self.query_one("#model-status").update("[red]Выберите провайдер[/red]")
            return
        try:
            from chip.api_validator import test_chat_completion
            ok, msg = test_chat_completion(self._current_provider, provider.api_key, provider.base_url, self.config.llm.model)
            self.query_one("#model-status").update(f"[green]✓ {msg}[/green]" if ok else f"[red]✗ {msg}[/red]")
        except Exception as e:
            self.query_one("#model-status").update(f"[red]✗ {e}[/red]")
    
    @on(Button.Pressed, "#download-btn")
    def handle_download(self):
        model = self.query_one("#download-input").value.strip()
        if not model:
            return
        self.query_one("#download-status").update(f"[yellow]Скачивание {model}...[/yellow]")
        try:
            result = subprocess.run(["ollama", "pull", model], capture_output=True, text=True, timeout=600)
            if result.returncode == 0:
                self.query_one("#download-status").update(f"[green]✓ {model} скачана[/green]")
                self._installed_models = get_installed_models()
            else:
                self.query_one("#download-status").update(f"[red]✗ {result.stderr[:100]}[/red]")
        except Exception as e:
            self.query_one("#download-status").update(f"[red]✗ {e}[/red]")
    
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
