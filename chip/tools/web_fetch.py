"""Web fetch tool for downloading content from URLs."""
from typing import Any
import requests
import re

from .base import BaseTool, ToolResult


class WebFetchTool(BaseTool):
    @property
    def name(self) -> str:
        return "web_fetch"

    @property
    def description(self) -> str:
        return "Fetch content from a URL (web page, API, file). Extracts readable text from HTML."

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
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9,ru;q=0.8"
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
                output = self._extract_text(response.text)
                if len(output) > 10000:
                    output = output[:10000] + f"\n\n[Truncated: total content longer]"

            return ToolResult(
                success=True,
                output=f"Status: {response.status_code}\nContent-Type: {response.headers.get('content-type', 'unknown')}\nURL: {url}\n\n{output}"
            )
        except requests.exceptions.Timeout:
            return ToolResult(success=False, output="", error=f"Request timed out after {timeout}s")
        except requests.exceptions.ConnectionError as e:
            return ToolResult(success=False, output="", error=f"Connection error: {e}")
        except requests.exceptions.HTTPError as e:
            return ToolResult(success=False, output="", error=f"HTTP error: {e.response.status_code}")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))

    def _extract_text(self, html: str) -> str:
        """Extract readable text from HTML."""
        # Remove scripts and styles
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL)
        
        # Extract meta description
        meta_desc = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]*)"', html)
        if meta_desc:
            html = f"<p>{meta_desc.group(1)}</p>\n{html}"
        
        # Replace common block elements with newlines
        html = re.sub(r'<(?:div|p|br|h[1-6]|li|tr)[^>]*>', '\n', html)
        html = re.sub(r'</(?:div|p|h[1-6]|li|tr)>', '\n', html)
        
        # Remove all remaining HTML tags
        text = re.sub(r'<[^>]+>', '', html)
        
        # Decode HTML entities
        import html
        text = html.unescape(text)
        text = text.replace('&quot;', '"').replace('&#x27;', "'").replace('&nbsp;', ' ')
        
        # Clean up whitespace
        lines = [line.strip() for line in text.splitlines()]
        lines = [line for line in lines if line and len(line) > 3]
        
        return '\n'.join(lines[:100])
