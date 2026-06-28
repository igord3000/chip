"""File reading tool."""
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class ReadFileTool(BaseTool):
    @property
    def name(self) -> str:
        return "read_file"

    @property
    def description(self) -> str:
        return "Read the contents of a file."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Path to the file to read."
                },
                "offset": {
                    "type": "integer",
                    "description": "Line number to start reading from (0-indexed). Default: 0.",
                    "default": 0
                },
                "limit": {
                    "type": "integer",
                    "description": "Maximum number of lines to read. Default: 2000.",
                    "default": 2000
                }
            },
            "required": ["path"]
        }

    def execute(self, path: str = "", offset: int = 0, limit: int = 2000) -> ToolResult:
        try:
            file_path = Path(path)
            if not file_path.exists():
                return ToolResult(success=False, output="", error=f"File not found: {path}")
            if not file_path.is_file():
                return ToolResult(success=False, output="", error=f"Not a file: {path}")

            with open(file_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()

            total_lines = len(lines)
            selected = lines[offset:offset + limit]

            output = ""
            for i, line in enumerate(selected, start=offset + 1):
                output += f"{i}: {line}"

            if offset > 0 or offset + limit < total_lines:
                output = f"Showing lines {offset + 1}-{min(offset + limit, total_lines)} of {total_lines}\n\n{output}"

            return ToolResult(success=True, output=output)
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
