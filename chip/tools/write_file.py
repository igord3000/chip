"""File writing tool."""
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class WriteFileTool(BaseTool):
    @property
    def name(self) -> str:
        return "write_file"

    @property
    def description(self) -> str:
        return "Write content to a file, creating it if it doesn't exist."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to write."
                },
                "content": {
                    "type": "string",
                    "description": "Content to write to the file."
                },
                "append": {
                    "type": "boolean",
                    "description": "If true, append to file instead of overwriting. Default: false.",
                    "default": False
                }
            },
            "required": ["path", "content"]
        }

    def execute(self, path: str = "", content: str = "", append: bool = False) -> ToolResult:
        try:
            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            mode = "a" if append else "w"
            with open(file_path, mode, encoding="utf-8") as f:
                f.write(content)

            action = "appended to" if append else "wrote to"
            return ToolResult(success=True, output=f"Successfully {action} {path}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
