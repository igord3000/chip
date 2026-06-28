"""Web search tool using DuckDuckGo Lite (works with all languages)."""
from typing import Any
import requests
import re
from urllib.parse import quote_plus

from .base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo (works with any language)."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search query."
                },
                "num_results": {
                    "type": "integer",
                    "description": "Number of results to return. Default: 5.",
                    "default": 5
                }
            },
            "required": ["query"]
        }

    def execute(self, query: str = "", num_results: int = 5) -> ToolResult:
        if not query:
            return ToolResult(success=False, output="", error="Query is required")

        # Try DuckDuckGo HTML search first
        results = self._search_ddg_html(query, num_results)
        
        # If no results, try the API
        if not results:
            results = self._search_ddg_api(query, num_results)

        if not results:
            return ToolResult(
                success=True,
                output=f"No results found for: {query}\n\nTip: Try using English or simpler keywords."
            )

        output = f"Search results for: {query}\n\n"
        for i, r in enumerate(results[:num_results], 1):
            output += f"{i}. {r['title']}\n"
            if r.get('snippet'):
                output += f"   {r['snippet'][:200]}\n"
            if r.get('url'):
                output += f"   URL: {r['url']}\n"
            output += "\n"

        return ToolResult(success=True, output=output)

    def _search_ddg_html(self, query: str, num_results: int) -> list[dict]:
        """Search using DuckDuckGo HTML (better for non-English)."""
        try:
            url = "https://html.duckduckgo.com/html/"
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Accept-Language": "en-US,en;q=0.9,ru;q=0.8"
            }
            data = {"q": query}
            
            response = requests.post(url, data=data, headers=headers, timeout=15)
            response.raise_for_status()
            
            results = []
            # Parse HTML results
            pattern = r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>(.*?)</a>.*?<a[^>]*class="result__snippet"[^>]*>(.*?)</a>'
            matches = re.findall(pattern, response.text, re.DOTALL)
            
            for href, title, snippet in matches[:num_results]:
                # Clean HTML tags
                title = re.sub(r'<[^>]+>', '', title).strip()
                snippet = re.sub(r'<[^>]+>', '', snippet).strip()
                # Decode URL
                if 'uddg=' in href:
                    from urllib.parse import unquote, parse_qs, urlparse
                    parsed = urlparse(href)
                    params = parse_qs(parsed.query)
                    href = unquote(params.get('uddg', [href])[0])
                
                results.append({
                    "title": title,
                    "snippet": snippet,
                    "url": href
                })
            
            return results
        except Exception:
            return []

    def _search_ddg_api(self, query: str, num_results: int) -> list[dict]:
        """Fallback: DuckDuckGo Instant Answer API."""
        try:
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_redirect": "1",
                "no_html": "1",
                "skip_disambig": "1"
            }
            response = requests.get(url, params=params, timeout=15)
            data = response.json()
            
            results = []
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", ""),
                    "snippet": data["AbstractText"],
                    "url": data.get("AbstractURL", "")
                })
            for topic in data.get("RelatedTopics", []):
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:100],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", "")
                    })
            return results[:num_results]
        except Exception:
            return []
