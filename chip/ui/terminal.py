"""Terminal UI with Rich library."""
from typing import Optional
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, BarColumn, TextColumn
from rich.table import Table
from rich.text import Text
from rich.live import Live
from rich.markdown import Markdown

from chip.context.tracker import ContextTracker


class TerminalUI:
    def __init__(self):
        self.console = Console()
        self._progress: Optional[Progress] = None

    def print_header(self, model: str, tools: list[str]):
        table = Table(show_header=False, box=None, padding=(0, 1))
        table.add_column("Key", style="cyan")
        table.add_column("Value")
        table.add_row("Model", model)
        table.add_row("Tools", ", ".join(tools))
        self.console.print(Panel(table, title="Chip Agent", border_style="blue"))

    def print_turn(self, turn: int):
        self.console.print(f"\n{'=' * 60}")
        self.console.print(f"[bold cyan]Turn {turn}[/bold cyan]")
        self.console.print(f"{'=' * 60}")

    def print_assistant_message(self, content: str):
        if content:
            self.console.print()
            self.console.print(Panel(
                Markdown(content) if "```" in content else content,
                title="Assistant",
                border_style="green"
            ))

    def print_tool_call(self, tool_name: str, arguments: dict):
        import json
        args_str = json.dumps(arguments, ensure_ascii=False, indent=2)
        self.console.print(f"\n[bold yellow]Tool:[/bold yellow] {tool_name}")
        self.console.print(f"[dim]{args_str}[/dim]")

    def print_tool_result(self, result: str, success: bool = True):
        style = "green" if success else "red"
        truncated = result[:500] + "..." if len(result) > 500 else result
        self.console.print(f"[{style}]Result:[/{style}] {truncated}")

    def print_context_meter(self, tracker: ContextTracker):
        percent = tracker.usage_percent * 100
        remaining = tracker.remaining_tokens
        status = tracker.status

        if status == "critical":
            color = "bold red"
            bar_color = "red"
            message = f"[bold red blink]CRITICAL: {percent:.1f}% used! {remaining} tokens remaining![/bold red blink]"
        elif status == "warning":
            color = "yellow"
            bar_color = "yellow"
            message = f"[yellow]WARNING: {percent:.1f}% used. {remaining} tokens remaining.[/yellow]"
        else:
            color = "green"
            bar_color = "green"
            message = f"[green]Context: {percent:.1f}% ({remaining} tokens left)[/green]"

        progress = Progress(
            TextColumn("[bold]{task.description}"),
            BarColumn(bar_width=40, complete_style=bar_color),
            TextColumn("{task.percentage:>3.0f}%"),
        )

        with progress:
            task = progress.add_task("Context", total=100, completed=percent)

        self.console.print(message)

        if status == "critical":
            self._show_checkpoint_prompt()

    def _show_checkpoint_prompt(self):
        self.console.print()
        self.console.print(Panel(
            "[bold red]Context window nearly full![/bold red]\n\n"
            "I recommend saving a checkpoint and starting a new session.\n"
            "This will preserve your progress and allow seamless continuation.",
            title="Save Session?",
            border_style="red"
        ))

    def print_checkpoint_saved(self, path: str):
        self.console.print(f"\n[green]Checkpoint saved to:[/green] {path}")
        self.console.print("[dim]Use --resume to continue from this checkpoint.[/dim]")

    def print_error(self, message: str):
        self.console.print(f"[bold red]Error:[/bold red] {message}")

    def print_warning(self, message: str):
        self.console.print(f"[yellow]Warning:[/yellow] {message}")

    def print_success(self, message: str):
        self.console.print(f"[green]{message}[/green]")

    def print_info(self, message: str):
        self.console.print(f"[dim]{message}[/dim]")

    def get_user_input(self) -> str:
        try:
            return input("\n[You] > ").strip()
        except (EOFError, KeyboardInterrupt):
            return ""

    def confirm(self, message: str) -> bool:
        try:
            response = input(f"\n{message} [Y/n] > ").strip().lower()
            return response in ("", "y", "yes")
        except (EOFError, KeyboardInterrupt):
            return False
