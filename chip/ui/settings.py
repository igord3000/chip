"""Settings screen for Chip agent - compact design."""
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
    """Compact settings panel."""
    
    CSS = """
    #settings-scroll {
        height: 1fr;
        overflow-y: auto;
        padding: 0 2;
    }
    
    .section {
        margin-top: 1;
        color: $accent;
        text-style: bold;
    }
    
    .row {
        height: auto;
        margin: 0;
    }
    
    Input {
        height: 3;
    }
    
    Select {
        height: 3;
    }
    
    Button {
        height: 3;
        min-width: 10;
    }
    
    Label {
        height: auto;
    }
    """
    
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
            # === GPU & Current Model ===
            gpu_text = f"GPU: {self.gpu.name} ({self.gpu.vram_gb:.0f}GB)" if self.gpu else "GPU: CPU mode"
            yield Label(f"[dim]{gpu_text}[/dim] | Модель: [bold]{self.config.llm.model}[/bold]", id="status-line")
            
            # === Provider ===
            yield Label("Провайдер", classes="section")
            with Horizontal(classes="row"):
                provider_options = [(f"{p.name}", key) for key, p in self.provider_manager.list_providers()]
                yield Select(provider_options, id="provider-select", prompt="...", value=self._current_provider)
            
            # === API Key ===
            yield Label("API ключ", classes="section")
            with Horizontal(classes="row"):
                yield Input(placeholder="API ключ...", id="api-key-input", password=True, classes="key-input")
                yield Button("Проверить", id="validate-btn", variant="default")
                yield Button("Сохранить", id="save-key-btn", variant="primary")
            yield Label("", id="key-status")
            
            # === Local Models ===
            yield Label("Локальные модели (Ollama)", classes="section")
            if self._installed_models:
                yield Select([(m, m) for m in self._installed_models], id="model-select", prompt="Выберите")
            else:
                yield Label("[dim]Нет моделей[/dim]")
            
            with Horizontal(classes="row"):
                yield Button("Обновить", id="refresh-btn")
                yield Button("Проверить", id="test-btn")
            yield Label("", id="model-status")
            
            # === Recommended ===
            recommended = get_recommended_models(self.gpu)
            if recommended:
                yield Label("Рекомендуемые", classes="section")
                for m in recommended[:4]:
                    mark = "✓" if m["name"] in self._installed_models else " "
                    yield Label(f" {mark} {m['name']} ({m['size_gb']}GB) {m['desc']}")
            
            # === Download ===
            yield Label("Скачать", classes="section")
            with Horizontal(classes="row"):
                yield Input(placeholder="qwen3:4b", id="dl-input")
                yield Button("Скачать", id="dl-btn")
            yield Label("", id="dl-status")
            
            # === Cloud ===
            yield Label("Облачные модели", classes="section")
            yield Select([
                ("GPT-4o Mini", "openai/gpt-4o-mini"),
                ("Claude 3.5", "anthropic/claude-3.5-sonnet"),
                ("Llama 3.1 8B", "meta-llama/llama-3.1-8b-instruct"),
                ("Gemini Flash", "google/gemini-2.0-flash-001"),
            ], id="cloud-select", prompt="Облачная модель")
            
            # === Max tokens ===
            with Horizontal(classes="row"):
                yield Label("Макс. токенов:")
                yield Input(value=str(self.config.llm.max_tokens), id="max-tokens-input", classes="small-input")
            
            # === Apply ===
            yield Button("Применить", id="apply-btn", variant="success")
    
    @on(Select.Changed, "#provider-select")
    def on_provider(self, e):
        if e.value:
            self._current_provider = e.value
            p = self.provider_manager.get_provider(e.value)
            if p:
                self.config.llm.base_url = p.base_url
    
    @on(Select.Changed, "#model-select")
    def on_model(self, e):
        if e.value:
            self.config.llm.model = e.value
            self._save()
    
    @on(Select.Changed, "#cloud-select")
    def on_cloud(self, e):
        if e.value:
            self.config.llm.model = e.value
            self._save()
    
    @on(Button.Pressed, "#refresh-btn")
    def on_refresh(self):
        self._installed_models = get_installed_models()
        self.query_one("#model-status").update(f"[green]✓ {len(self._installed_models)} моделей[/green]")
    
    @on(Button.Pressed, "#validate-btn")
    def on_validate(self):
        self.query_one("#key-status").update("[yellow]...[/yellow]")
        p = self.provider_manager.get_provider(self._current_provider)
        if not p:
            self.query_one("#key-status").update("[red]Выберите провайдер[/red]")
            return
        key = self.query_one("#api-key-input").value.strip() or p.api_key
        try:
            from chip.api_validator import validate_api_key
            ok, msg = validate_api_key(self._current_provider, key, p.base_url)
            self.query_one("#key-status").update(f"[green]✓ {msg}[/green]" if ok else f"[red]✗ {msg}[/red]")
        except Exception as e:
            self.query_one("#key-status").update(f"[red]✗ {e}[/red]")
    
    @on(Button.Pressed, "#save-key-btn")
    def on_save_key(self):
        key = self.query_one("#api-key-input").value.strip()
        if not key:
            self.query_one("#key-status").update("[red]Введите ключ[/red]")
            return
        p = self.provider_manager.get_provider(self._current_provider)
        if p:
            p.api_key = key
            self.provider_manager._save()
            self.config.llm.api_key = key
            self.query_one("#key-status").update("[green]✓[/green]")
    
    @on(Button.Pressed, "#test-btn")
    def on_test(self):
        self.query_one("#model-status").update("[yellow]...[/yellow]")
        p = self.provider_manager.get_provider(self._current_provider)
        if not p:
            self.query_one("#model-status").update("[red]Выберите провайдер[/red]")
            return
        try:
            from chip.api_validator import test_chat_completion
            ok, msg = test_chat_completion(self._current_provider, p.api_key, p.base_url, self.config.llm.model)
            self.query_one("#model-status").update(f"[green]✓ {msg}[/green]" if ok else f"[red]✗ {msg}[/red]")
        except Exception as e:
            self.query_one("#model-status").update(f"[red]✗ {e}[/red]")
    
    @on(Button.Pressed, "#dl-btn")
    def on_download(self):
        model = self.query_one("#dl-input").value.strip()
        if not model:
            return
        self.query_one("#dl-status").update(f"[yellow]...[/yellow]")
        try:
            r = subprocess.run(["ollama", "pull", model], capture_output=True, text=True, timeout=600)
            if r.returncode == 0:
                self.query_one("#dl-status").update(f"[green]✓ {model}[/green]")
                self._installed_models = get_installed_models()
            else:
                self.query_one("#dl-status").update(f"[red]✗ {r.stderr[:80]}[/red]")
        except Exception as e:
            self.query_one("#dl-status").update(f"[red]✗ {e}[/red]")
    
    @on(Button.Pressed, "#apply-btn")
    def on_apply(self):
        try:
            self.config.llm.max_tokens = int(self.query_one("#max-tokens-input").value)
        except ValueError:
            pass
        self._save()
        self.query_one("#model-status").update("[green]✓[/green]")
    
    def _save(self):
        p = Path.home() / ".chip" / "config.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            json.dump({
                "model": self.config.llm.model,
                "base_url": self.config.llm.base_url,
                "api_key": self.config.llm.api_key,
                "max_tokens": self.config.llm.max_tokens,
            }, f)
