"""Web search tool using DuckDuckGo."""
from typing import Any
import requests

from .base import BaseTool, ToolResult


class WebSearchTool(BaseTool):
    @property
    def name(self) -> str:
        return "web_search"

    @property
    def description(self) -> str:
        return "Search the web using DuckDuckGo."

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
            response.raise_for_status()
            data = response.json()

            results = []

            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", ""),
                    "snippet": data["AbstractText"],
                    "url": data.get("AbstractURL", "")
                })

            for topic in data.get("RelatedTopics", [])[:num_results]:
                if isinstance(topic, dict) and "Text" in topic:
                    results.append({
                        "title": topic.get("Text", "")[:100],
                        "snippet": topic.get("Text", ""),
                        "url": topic.get("FirstURL", "")
                    })

            if not results:
                results = [{"title": "No results", "snippet": f"No results found for: {query}", "url": ""}]

            output = f"Search results for: {query}\n\n"
            for i, r in enumerate(results[:num_results], 1):
                output += f"{i}. {r['title']}\n"
                if r['snippet']:
                    output += f"   {r['snippet'][:200]}\n"
                if r['url']:
                    output += f"   URL: {r['url']}\n"
                output += "\n"

            return ToolResult(success=True, output=output)
        except requests.exceptions.Timeout:
            return ToolResult(success=False, output="", error="Search timed out")
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
