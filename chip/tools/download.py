"""Download tool for saving files from URLs."""
from typing import Any
from pathlib import Path
import requests

from .base import BaseTool, ToolResult


class DownloadTool(BaseTool):
    @property
    def name(self) -> str:
        return "download"

    @property
    def description(self) -> str:
        return "Download a file from a URL and save it locally."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "URL to download from."
                },
                "path": {
                    "type": "string",
                    "description": "Local path to save the file. Default: filename from URL."
                },
                "timeout": {
                    "type": "integer",
                    "description": "Download timeout in seconds. Default: 60.",
                    "default": 60
                }
            },
            "required": ["url"]
        }

    def execute(self, url: str = "", path: str = "", timeout: int = 60) -> ToolResult:
        if not url:
            return ToolResult(success=False, output="", error="URL is required")

        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; ChipAgent/1.0)"
            }

            response = requests.get(url, headers=headers, timeout=timeout, stream=True)
            response.raise_for_status()

            if not path:
                from urllib.parse import urlparse
                parsed = urlparse(url)
                path = Path(parsed.path).name or "downloaded_file"

            file_path = Path(path)
            file_path.parent.mkdir(parents=True, exist_ok=True)

            total_size = 0
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
                        total_size += len(chunk)

            size_str = self._human_size(total_size)
            return ToolResult(
                success=True,
                output=f"Downloaded: {url}\nSaved to: {file_path.absolute()}\nSize: {size_str}"
            )
        except requests.exceptions.Timeout:
            return ToolResult(success=False, output="", error=f"Download timed out after {timeout}s")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    @staticmethod
    def _human_size(size: int) -> str:
        for unit in ["B", "KB", "MB", "GB"]:
            if size < 1024:
                return f"{size:.1f}{unit}"
            size /= 1024
        return f"{size:.1f}TB"
