"""Bash tool for executing shell commands."""
import subprocess
from typing import Any

from .base import BaseTool, ToolResult


class BashTool(BaseTool):
    def __init__(self, timeout: int = 120):
        self.timeout = timeout

    @property
    def name(self) -> str:
        return "bash"

    @property
    def description(self) -> str:
        return "Execute a shell command and return the output."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The bash command to execute."
                }
            },
            "required": ["command"]
        }

    def execute(self, command: str = "") -> ToolResult:
        if not command.strip():
            return ToolResult(success=False, output="", error="Empty command")

        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=self.timeout
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"

            return ToolResult(
                success=result.returncode == 0,
                output=f"Exit code: {result.returncode}\n{output}" if output else f"Exit code: {result.returncode}",
                error=None if result.returncode == 0 else f"Exit code: {result.returncode}"
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                output="",
                error=f"Command timed out after {self.timeout}s"
            )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
