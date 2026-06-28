"""Textual-based GUI for Chip agent."""
import json
from pathlib import Path
from typing import Optional

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.widgets import (
    Header, Footer, Static, Input, Button,
    DataTable, Label, ProgressBar, RichLog
)
from textual.binding import Binding
from textual import on

from chip.config import load_config
from chip.llm import LLMClient
from chip.tools import ToolRegistry
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
        yield Label(self.content, classes="msg-content")


class ToolCallWidget(Static):
    """Display a tool call."""
    
    def __init__(self, tool_name: str, arguments: dict, result: str):
        super().__init__()
        self.tool_name = tool_name
        self.arguments = arguments
        self.result = result
    
    def compose(self) -> ComposeResult:
        args_str = json.dumps(self.arguments, ensure_ascii=False)
        if len(args_str) > 100:
            args_str = args_str[:100] + "..."
        
        yield Label(f"[yellow]🔧 {self.tool_name}[/yellow]", classes="tool-header")
        yield Label(f"[dim]{args_str}[/dim]", classes="tool-args")
        
        result_style = "green" if "Error" not in self.result else "red"
        truncated = self.result[:200] + "..." if len(self.result) > 200 else self.result
        yield Label(f"[{result_style}]{truncated}[/{result_style}]", classes="tool-result")


class ChipApp(App):
    """Main Chip application."""
    
    CSS = """
    Screen {
        layout: vertical;
    }
    
    #chat-container {
        height: 1fr;
        overflow-y: auto;
        padding: 1;
    }
    
    #input-container {
        height: 3;
        padding: 1;
    }
    
    #user-input {
        width: 1fr;
    }
    
    .msg-header {
        margin-bottom: 0;
    }
    
    .msg-content {
        margin-bottom: 1;
        padding-left: 2;
    }
    
    .tool-header {
        margin-top: 0;
    }
    
    .tool-args {
        padding-left: 2;
    }
    
    .tool-result {
        padding-left: 2;
        margin-bottom: 1;
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
        Binding("ctrl+c", "clear_chat", "Clear Chat"),
        Binding("ctrl+s", "save_session", "Save Session"),
    ]
    
    def __init__(self, model: str = "qwen3:1.7b"):
        super().__init__()
        self.model = model
        self.config = load_config()
        self.llm = LLMClient(self.config.llm)
        self.tools = ToolRegistry(bash_timeout=self.config.bash_timeout)
        self.tracker = ContextTracker(max_tokens=32000)
        self.response_cache = ResponseCache(Path.home() / ".chip" / "cache")
        self.semantic_cache = SemanticCache()
        self.messages: list[dict] = []
        self.cache_hits = 0
    
    def compose(self) -> ComposeResult:
        yield StatusBar(self.model)
        yield Header(show_clock=True)
        yield ScrollableContainer(id="chat-container")
        with Horizontal(id="input-container"):
            yield Input(placeholder="Type your message...", id="user-input")
            yield Button("Send", id="send-btn", variant="primary")
        yield Footer()
    
    @on(Input.Submitted, "#user-input")
    @on(Button.Pressed, "#send-btn")
    async def handle_send(self):
        """Handle send button or Enter key."""
        input_widget = self.query_one("#user-input")
        message = input_widget.value.strip()
        
        if not message:
            return
        
        input_widget.value = ""
        
        # Add user message to UI
        chat_container = self.query_one("#chat-container")
        chat_container.mount(ChatMessage("user", message))
        
        # Add to messages
        self.messages.append({"role": "user", "content": message})
        
        # Check cache first
        cached = self.response_cache.get(self.messages)
        if not cached:
            cached = self.semantic_cache.get(message)
        
        if cached:
            self.cache_hits += 1
            chat_container.mount(ChatMessage("assistant", f"[cached] {cached}"))
            self._update_status()
            return
        
        # Get response from LLM
        try:
            response = self.llm.chat(self.messages, self.tools.to_openai_tools())
            
            if response.content:
                chat_container.mount(ChatMessage("assistant", response.content))
                self.messages.append({"role": "assistant", "content": response.content})
                
                # Cache the response
                self.response_cache.set(self.messages, response.content)
                self.semantic_cache.set(message, response.content)
            
            # Handle tool calls
            for tool_call in (response.tool_calls or []):
                func_name = tool_call["function"]["name"]
                arguments = json.loads(tool_call["function"]["arguments"])
                
                result = self.tools.call(func_name, arguments)
                
                chat_container.mount(ToolCallWidget(
                    func_name, arguments, result.output
                ))
                
                self.messages.append({
                    "role": "assistant",
                    "content": response.content or None,
                    "tool_calls": [tool_call]
                })
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result.output
                })
            
            self._update_status()
            
        except Exception as e:
            chat_container.mount(ChatMessage("assistant", f"[red]Error: {e}[/red]"))
        
        # Scroll to bottom
        chat_container.scroll_end()
    
    def _update_status(self):
        """Update status bar."""
        tokens = self.tracker.update(self.messages)
        stats = self.response_cache.stats()
        
        status_bar = self.query_one(StatusBar)
        status_bar.update_stats(
            tokens_used=tokens,
            tokens_total=self.tracker.max_tokens,
            cache_hits=self.cache_hits
        )
    
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
        
        checkpoint_dir = self.config.checkpoint_dir
        manager = CheckpointManager(checkpoint_dir)
        path = manager.save(self.messages, "", {"tokens_used": self.tracker.current_tokens})
        
        chat_container = self.query_one("#chat-container")
        chat_container.mount(ChatMessage("assistant", f"Session saved: {path}"))
        chat_container.scroll_end()


def main():
    """Run the Chip Textual app."""
    import sys
    
    model = sys.argv[1] if len(sys.argv) > 1 else "qwen3:1.7b"
    app = ChipApp(model=model)
    app.run()


if __name__ == "__main__":
    main()
