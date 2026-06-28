"""Web fetch tool for downloading content from URLs."""
from typing import Any
import requests

from .base import BaseTool, ToolResult


class WebFetchTool(BaseTool):
    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch content from a URL (web page, API, file)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string",
                    "description": "The URL to fetch."
                },
                "format": {
                    "type": "string",
                    "description": "Return format: 'text' (default), 'html', 'json'.",
                    "enum": ["text", "html", "json"],
                    "default": "text"
                },
                "timeout": {
                    "type": "integer",
                    "description": "Request timeout in seconds. Default: 30.",
                    "default": 30
                }
            },
            "required": ["url"]
        }

    def execute(self, url: str = "", format: str = "text", timeout: int = 30) -> ToolResult:
        if not url:
            return ToolResult(success=False, output="", error="URL is required")

        try:
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            headers = {
                "User-Agent": "Mozilla/5.0 (compatible; ChipAgent/1.0)"
            }

            response = requests.get(url, headers=headers, timeout=timeout, allow_redirects=True)
            response.raise_for_status()

            if format == "json":
                try:
                    data = response.json()
                    import json
                    output = json.dumps(data, indent=2, ensure_ascii=False)
                except Exception:
                    output = response.text
            elif format == "html":
                output = response.text
            else:
                output = response.text
                if len(output) > 10000:
                    output = output[:10000] + f"\n\n[Truncated: {len(response.text)} total chars]"

            return ToolResult(
                success=True,
                output=f"Status: {response.status_code}\nContent-Type: {response.headers.get('content-type', 'unknown')}\n\n{output}"
            )
        except requests.exceptions.Timeout:
            return ToolResult(success=False, output="", error=f"Request timed out after {timeout}s")
        except requests.exceptions.ConnectionError as e:
            return ToolResult(success=False, output="", error=f"Connection error: {e}")
        except requests.exceptions.HTTPError as e:
            return ToolResult(success=False, output="", error=f"HTTP error: {e.response.status_code}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
