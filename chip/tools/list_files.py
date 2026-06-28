"""Directory listing tool."""
from pathlib import Path
from typing import Any

from .base import BaseTool, ToolResult


class ListFilesTool(BaseTool):
    @property
    def name(self) -> str:
        return "list_files"

    @property
    def description(self) -> str:
        return "List files and directories in a given path."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list. Default: current directory.",
                    "default": "."
                },
                "pattern": {
                    "type": "string",
                    "description": "Glob pattern to filter files (e.g., '*.py'). Default: all files.",
                    "default": "*"
                },
                "recursive": {
                    "type": "boolean",
                    "description": "If true, list files recursively. Default: false.",
                    "default": False
                }
            },
            "required": []
        }

    def execute(self, path: str = ".", pattern: str = "*", recursive: bool = False) -> ToolResult:
        try:
            dir_path = Path(path)
            if not dir_path.exists():
                return ToolResult(success=False, output="", error=f"Path not found: {path}")
            if not dir_path.is_dir():
                return ToolResult(success=False, output="", error=f"Not a directory: {path}")

            if recursive:
                files = sorted(dir_path.rglob(pattern))
            else:
                files = sorted(dir_path.glob(pattern))

            output = ""
            for f in files:
                rel = f.relative_to(dir_path)
                prefix = "  " if f.is_file() else "  [DIR]"
                size = f.stat().st_size if f.is_file() else 0
                if f.is_file():
                    output += f"{prefix} {rel} ({self._human_size(size)})\n"
                else:
                    output += f"{prefix} {rel}/\n"

            if not output:
                output = f"No files matching '{pattern}' in {path}"

            return ToolResult(success=True, output=output.strip())
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    @staticmethod
    def _human_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
