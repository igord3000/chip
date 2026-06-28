"""Interactive chat TUI with token tracking."""
import json
import os
from pathlib import Path
from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.markdown import Markdown
from rich.layout import Layout
from rich.align import Align
from prompt_toolkit import PromptSession
from prompt_toolkit.history import FileHistory

from chip.context.tracker import ContextTracker


class ChatUI:
    def __init__(self, model: str, tools: list[str], checkpoint_dir: Path):
        self.console = Console()
        self.model = model
        self.tools = tools
        self.checkpoint_dir = checkpoint_dir
        self.history_file = checkpoint_dir / ".chat_history"
        self.session = PromptSession(history=FileHistory(str(self.history_file)))
        self._messages: list[dict] = []

    def print_welcome(self):
        self.console.clear()
        
        header = Table(show_header=False, box=None, padding=(0, 1))
        header.add_column("Key", style="cyan bold")
        header.add_column("Value")
        header.add_row("Model", self.model)
        header.add_row("Tools", ", ".join(self.tools))
        
        self.console.print(Panel(header, title="[bold blue]Chip Agent[/bold blue]", border_style="blue"))
        self.console.print("[dim]Type your message. Commands: /exit, /save, /clear, /sessions[/dim]\n")

    def print_token_bar(self, tracker: ContextTracker):
        percent = tracker.usage_percent * 100
        remaining = tracker.remaining_tokens
        status = tracker.status
        
        if status == "critical":
            color = "red"
            style = "bold red"
        elif status == "warning":
            color = "yellow"
            style = "yellow"
        else:
            color = "green"
            style = "green"
        
        bar_width = 40
        filled = int(bar_width * tracker.usage_percent)
        bar = "█" * filled + "░" * (bar_width - filled)
        
        self.console.print(f"\n[{style}]{bar} {percent:.0f}% | {remaining:,} tokens left[/{style}]")

    def print_user_message(self, message: str):
        self.console.print(f"\n[bold cyan]You:[/bold cyan] {message}")

    def print_assistant_message(self, content: str):
        if content:
            self.console.print()
            if "```" in content:
                self.console.print(Panel(Markdown(content), border_style="green"))
            else:
                self.console.print(Panel(content, border_style="green", title="[green]Chip[/green]"))

    def print_tool_call(self, tool_name: str, arguments: dict):
        args_str = json.dumps(arguments, ensure_ascii=False)
        if len(args_str) > 100:
            args_str = args_str[:100] + "..."
        self.console.print(f"  [yellow]→ {tool_name}[/yellow] [dim]{args_str}[/dim]")

    def print_tool_result(self, result: str, success: bool = True):
        style = "green" if success else "red"
        truncated = result[:300] + "..." if len(result) > 300 else result
        self.console.print(f"  [{style}]✓ {truncated}[/{style}]")

    def print_error(self, message: str):
        self.console.print(f"\n[red]Error: {message}[/red]")

    def print_info(self, message: str):
        self.console.print(f"[dim]{message}[/dim]")

    def print_session_saved(self, path: str):
        self.console.print(f"[green]Session saved: {path}[/green]")

    def get_input(self) -> str:
        try:
            return self.session.prompt("\n[You] > ").strip()
        except (EOFError, KeyboardInterrupt):
            return "/exit"

    def clear_screen(self):
        self.console.clear()
        self.print_welcome()
