"""Subagent tool for spawning sub-tasks."""
from typing import Any

from .base import BaseTool, ToolResult


class SubagentTool(BaseTool):
    def __init__(self, manager=None):
        self._manager = manager

    @property
    def name(self) -> str:
        return "subagent"

    @property
    def description(self) -> str:
        return "Spawn a subagent to handle a sub-task in parallel."

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "prompt": {
                    "type": "string",
                    "description": "The task prompt for the subagent."
                },
                "parallel": {
                    "type": "boolean",
                    "description": "If true, spawn multiple subagents for different parts. Default: false.",
                    "default": False
                }
            },
            "required": ["prompt"]
        }

    def execute(self, prompt: str = "", parallel: bool = False) -> ToolResult:
        if not self._manager:
            return ToolResult(
                success=False,
                output="",
                error="SubagentManager not initialized"
            )

        try:
            if parallel and "\n" in prompt:
                prompts = [p.strip() for p in prompt.split("\n") if p.strip()]
                results = self._manager.run_parallel(prompts)
                
                output = "Parallel subagent results:\n\n"
                for r in results:
                    status = "✓" if r.success else "✗"
                    output += f"{status} [{r.task_id}]: {r.output[:200]}\n\n"
                
                return ToolResult(success=True, output=output)
            else:
                task_id = self._manager.spawn(prompt)
                result = self._manager.run_task(task_id)
                
                return ToolResult(
                    success=result.success,
                    output=f"Subagent [{result.task_id}]: {result.output}"
                )
        except Exception as e:
            return ToolResult(success=False, output="", error=str(e))
