"""Textual-based GUI for Chip agent with activity panel."""
import json
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, Input, Button, Label, RichLog
)
from textual.binding import Binding
from textual import on

from chip.config import load_config
from chip.context.tracker import ContextTracker
from chip.cache import ResponseCache, SemanticCache


class StatusBar(Static):
    """Status bar showing model, tokens, cache stats."""
    
    def __init__(self, model: str):
        super().__init__()
        self.model = model
        self.tokens_used = 0
        self.tokens_total = 32000
        self.cache_hits = 0
    
    def compose(self) -> ComposeResult:
        yield Label(f"Model: {self.model}", id="model-label")
        yield Label("Tokens: 0/32000", id="tokens-label")
        yield Label("Cache: 0 hits", id="cache-label")
    
    def update_stats(self, tokens_used: int, tokens_total: int, cache_hits: int):
        self.tokens_used = tokens_used
        self.tokens_total = tokens_total
        self.cache_hits = cache_hits
        percent = (tokens_used / tokens_total * 100) if tokens_total > 0 else 0
        self.query_one("#tokens-label").update(f"Tokens: {tokens_used}/{tokens_total} ({percent:.0f}%)")
        self.query_one("#cache-label").update(f"Cache: {cache_hits} hits")


class ChatMessage(Static):
    """A single chat message."""
    
    def __init__(self, role: str, content: str):
        super().__init__()
        self.role = role
        self.content = content
    
    def compose(self) -> ComposeResult:
        style = "bold cyan" if self.role == "user" else "bold green"
        icon = "👤" if self.role == "user" else "🤖"
        yield Label(f"[{style}]{icon} {self.role.upper()}[/{style}]", classes="msg-header")
        # Show content as plain text with Rich markup
        yield Label(self.content, classes="msg-content")


class ActivityPanel(Static):
    """Right panel showing LLM activity."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self._log_widget = None
        self._log_lines = []
    
    def compose(self) -> ComposeResult:
        yield Label("[bold]Активность (Ctrl+Shift+C для копирования)[/bold]", id="activity-title")
        yield RichLog(id="activity-log", highlight=True, markup=True, wrap=True)
    
    def log_event(self, message: str):
        """Add event to activity log."""
        if self._log_widget is None:
            try:
                self._log_widget = self.query_one("#activity-log")
                # Enable text selection after mount
                self._log_widget.allow_select = True
            except Exception:
                return
        self._log_lines.append(message)
        self._log_widget.write(message)
    
    def get_all_text(self) -> str:
        """Get all log text for copying."""
        return "\n".join(self._log_lines)


class ChipApp(App):
    """Main Chip application."""
    
    CSS = """
    Screen {
        layout: horizontal;
    }
    
    #main-panel {
        width: 2fr;
        height: 1fr;
        layout: vertical;
    }
    
    #activity-panel {
        width: 1fr;
        height: 1fr;
        border-left: solid $primary;
        padding: 1;
    }
    
    #activity-title {
        dock: top;
        text-align: center;
        background: $accent-darken-2;
        color: white;
        height: 1;
    }
    
    #activity-log {
        height: 1fr;
    }
    
    #chat-container {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    
    #settings-scroll {
        height: 1fr;
        overflow-y: auto;
        padding: 0 2;
    }
    
    #input-container {
        dock: bottom;
        height: auto;
        min-height: 3;
        padding: 0 1;
        background: $surface;
        border-top: solid $primary;
    }
    
    #user-input {
        width: 1fr;
        height: 3;
    }
    
    #send-btn {
        width: auto;
        min-width: 10;
        height: 3;
    }
    
    #settings-btn {
        width: auto;
        min-width: 3;
        height: 3;
    }
    
    .msg-header {
        margin-bottom: 0;
    }
    
    .msg-content {
        margin-bottom: 1;
        padding-left: 2;
    }
    
    StatusBar {
        dock: top;
        height: 1;
        background: $accent-darken-2;
        color: white;
        padding: 0 1;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+q", "quit", "Quit"),
        Binding("ctrl+c", "clear_chat", "Clear"),
        Binding("ctrl+s", "save_session", "Save"),
        Binding("ctrl+comma", "show_settings", "Settings"),
        Binding("ctrl+r", "reload", "Reload"),
        Binding("ctrl+shift+c", "copy_activity", "Copy Log"),
    ]
    
    def __init__(self, model: str = None):
        super().__init__()
        self.config = load_config()
        self.model = model or self.config.llm.model
        self.tracker = ContextTracker(max_tokens=32000)
        self.response_cache = ResponseCache(Path.home() / ".chip" / "cache")
        self.semantic_cache = SemanticCache()
        self.messages: list[dict] = []
        self.cache_hits = 0
        self.activity: Optional[ActivityPanel] = None
        self.showing_settings = False
    
    def compose(self) -> ComposeResult:
        yield StatusBar(self.model)
        with Horizontal():
            with Vertical(id="main-panel"):
                yield ScrollableContainer(id="chat-container")
                with Horizontal(id="input-container"):
                    yield Input(placeholder="Введите сообщение...", id="user-input")
                    yield Button("Отправить", id="send-btn", variant="primary")
                    yield Button("⚙", id="settings-btn", variant="default")
            yield ActivityPanel(id="activity-panel")
    
    def log_activity(self, message: str, style: str = ""):
        """Log activity to side panel."""
        if self.activity is None:
            try:
                self.activity = self.query_one("#activity-panel")
            except Exception:
                return
        
        if style:
            message = f"[{style}]{message}[/{style}]"
        self.activity.log_event(message)
    
    @on(Button.Pressed, "#settings-btn")
    def handle_settings(self):
        """Toggle settings panel."""
        self.action_show_settings()
    
    def action_show_settings(self):
        """Show settings screen."""
        from chip.ui.settings import SettingsScreen
        
        chat_container = self.query_one("#chat-container")
        
        if self.showing_settings:
            # Remove settings, show chat
            for child in chat_container.children:
                if isinstance(child, SettingsScreen):
                    child.remove()
            self.showing_settings = False
            
            # Reload config from file
            from chip.config import load_config
            self.config = load_config()
            
            # Update LLM client
            from chip.llm import LLMClient
            self.llm = LLMClient(self.config.llm)
            
            # Update status bar
            self.query_one(StatusBar).model = self.config.llm.model
            self.query_one("#model-label").update(f"Model: {self.config.llm.model}")
            
            self.log_activity(f"Модель: {self.config.llm.model}", "green")
        else:
            # Hide chat messages, show settings
            for child in chat_container.children:
                child.display = False
            
            settings = SettingsScreen(self.config)
            chat_container.mount(settings)
            self.showing_settings = True
    
    @on(Input.Submitted, "#user-input")
    @on(Button.Pressed, "#send-btn")
    async def handle_send(self):
        """Handle send button or Enter key."""
        input_widget = self.query_one("#user-input")
        message = input_widget.value.strip()
        
        if not message:
            return
        
        input_widget.value = ""
        
        chat_container = self.query_one("#chat-container")
        chat_container.mount(ChatMessage("user", message))
        chat_container.scroll_end()
        
        self.messages.append({"role": "user", "content": message})
        self.log_activity(f"Запрос: {message}", "bold cyan")
        
        # Check cache
        cached = self.response_cache.get(self.messages)
        if not cached:
            cached = self.semantic_cache.get(message)
        
        if cached:
            self.cache_hits += 1
            chat_container.mount(ChatMessage("assistant", f"[cached] {cached}"))
            chat_container.scroll_end()
            self.log_activity("Ответ из кэша", "green")
            self._update_status()
            return
        
        self.log_activity("Обработка...", "yellow")
        
        # Use universal agent
        from chip.universal_agent import UniversalAgent
        agent = UniversalAgent(self.config)
        
        result = agent.execute(message, callback=lambda msg: self.log_activity(msg, "cyan"))
        
        if result.success:
            chat_container.mount(ChatMessage("assistant", result.answer))
            self.messages.append({"role": "assistant", "content": result.answer})
            self.response_cache.set(self.messages, result.answer)
            self.semantic_cache.set(message, result.answer)
            
            if result.tools_called:
                self.log_activity(f"Инструменты: {', '.join(result.tools_called)}", "green")
        
        self._update_status()
    
    def _update_status(self):
        """Update status bar."""
        tokens = self.tracker.update(self.messages)
        stats = self.response_cache.stats()
        status_bar = self.query_one(StatusBar)
        status_bar.update_stats(tokens, self.tracker.max_tokens, self.cache_hits)
    
    def action_clear_chat(self):
        """Clear chat history."""
        chat_container = self.query_one("#chat-container")
        chat_container.remove_children()
        self.messages = []
        self.tracker = ContextTracker(max_tokens=32000)
        self.cache_hits = 0
        self._update_status()
    
    def action_save_session(self):
        """Save current session."""
        from chip.context.checkpoint import CheckpointManager
        manager = CheckpointManager(self.config.checkpoint_dir)
        path = manager.save(self.messages, "", {"tokens": self.tracker.current_tokens})
        self.log_activity(f"Сессия сохранена: {path}", "green")
    
    def action_copy_activity(self):
        """Copy all activity log to clipboard or file."""
        try:
            activity = self.query_one("#activity-panel")
            text = activity.get_all_text()
            if not text:
                self.log_activity("Нет текста для копирования", "yellow")
                return
            
            # Try xclip first
            try:
                import subprocess
                process = subprocess.Popen(['xclip', '-selection', 'clipboard'], stdin=subprocess.PIPE)
                process.communicate(text.encode())
                self.log_activity("✓ Скопировано в буфер обмена", "green")
                return
            except Exception:
                pass
            
            # Save to file in Windows-accessible path
            log_file = Path("/mnt/c/Users/user/chip/activity_log.txt")
            log_file.parent.mkdir(parents=True, exist_ok=True)
            with open(log_file, "w", encoding="utf-8") as f:
                f.write(text)
            self.log_activity(f"✓ Сохранено: {log_file}", "green")
            
        except Exception as e:
            self.log_activity(f"Ошибка: {e}", "red")
    
    def action_reload(self):
        """Reload the application."""
        import subprocess
        import sys
        # Start new process and exit current
        subprocess.Popen([sys.executable, "-m", "chip"])
        self.exit()


def main():
    import sys
    model = sys.argv[1] if len(sys.argv) > 1 else None
    app = ChipApp(model=model)
    app.run()


if __name__ == "__main__":
    main()
