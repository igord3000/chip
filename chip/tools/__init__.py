"""Tool registry and manager."""
from typing import Any

from .base import BaseTool, ToolResult
from .bash import BashTool
from .read_file import ReadFileTool
from .write_file import WriteFileTool
from .list_files import ListFilesTool
from .subagent import SubagentTool
from .web_fetch import WebFetchTool
from .web_search import WebSearchTool
from .download import DownloadTool


class ToolRegistry:
    def __init__(self, bash_timeout: int = 120, subagent_manager=None):
        self._tools: dict[str, BaseTool] = {}
        self._register_default_tools(bash_timeout, subagent_manager)

    def _register_default_tools(self, bash_timeout: int, subagent_manager=None):
        self.register(BashTool(timeout=bash_timeout))
        self.register(ReadFileTool())
        self.register(WriteFileTool())
        self.register(ListFilesTool())
        self.register(SubagentTool(manager=subagent_manager))
        self.register(WebFetchTool())
        self.register(WebSearchTool())
        self.register(DownloadTool())

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str) -> BaseTool | None:
        return self._tools.get(name)

    def call(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        tool = self.get(name)
        if not tool:
            return ToolResult(
                success=False,
                output="",
                error=f"Unknown tool: {name}. Available: {', '.join(self._tools.keys())}"
            )
        try:
            return tool.execute(**arguments)
        except Exception as e:
            return ToolResult(success=False, output="", error=f"Error calling {name}: {e}")

    def to_openai_tools(self) -> list[dict]:
        return [tool.to_openai_tool() for tool in self._tools.values()]

    @property
    def tool_names(self) -> list[str]:
        return list(self._tools.keys())
