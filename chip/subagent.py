"""Subagent system for parallel task execution."""
import json
import uuid
from dataclasses import dataclass, field
from typing import Any, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from chip.config import AgentConfig, load_config
from chip.llm import LLMClient
from chip.tools import ToolRegistry


@dataclass
class SubagentTask:
    id: str
    prompt: str
    status: str = "pending"
    result: Optional[str] = None
    error: Optional[str] = None
    messages: list[dict] = field(default_factory=list)


@dataclass
class SubagentResult:
    task_id: str
    success: bool
    output: str
    messages: list[dict]


class SubagentManager:
    def __init__(self, config: Optional[AgentConfig] = None, max_workers: int = 3):
        self.config = config or load_config()
        self.llm = LLMClient(self.config.llm)
        self.tools = ToolRegistry(bash_timeout=self.config.bash_timeout)
        self.max_workers = max_workers
        self.tasks: dict[str, SubagentTask] = {}
        self._checkpoint_dir = self.config.checkpoint_dir / "subagents"
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def spawn(self, prompt: str, task_id: Optional[str] = None) -> str:
        task_id = task_id or str(uuid.uuid4())[:8]
        task = SubagentTask(id=task_id, prompt=prompt)
        self.tasks[task_id] = task
        return task_id

    def run_task(self, task_id: str) -> SubagentResult:
        task = self.tasks.get(task_id)
        if not task:
            return SubagentResult(
                task_id=task_id,
                success=False,
                output=f"Task {task_id} not found",
                messages=[]
            )

        task.status = "running"
        
        system_prompt = f"""You are a subagent. Your task: {task.prompt}

You have access to tools: bash, read_file, write_file, list_files.
Complete the task and return your final answer.
Be concise and focused on the task."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": task.prompt}
        ]

        for turn in range(1, self.config.max_turns + 1):
            try:
                response = self.llm.chat(messages, self.tools.to_openai_tools())
            except Exception as e:
                task.status = "failed"
                task.error = str(e)
                return SubagentResult(
                    task_id=task_id,
                    success=False,
                    output=f"LLM error: {e}",
                    messages=messages
                )

            if response.content and not response.tool_calls:
                task.status = "completed"
                task.result = response.content
                messages.append({"role": "assistant", "content": response.content})
                
                self._save_checkpoint(task_id, messages)
                
                return SubagentResult(
                    task_id=task_id,
                    success=True,
                    output=response.content,
                    messages=messages
                )

            for tool_call in (response.tool_calls or []):
                func_name = tool_call["function"]["name"]
                try:
                    arguments = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}

                result = self.tools.call(func_name, arguments)
                
                messages.append({
                    "role": "assistant",
                    "content": response.content or None,
                    "tool_calls": [tool_call]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result.output if result.success else f"Error: {result.error}"
                })

        task.status = "completed"
        task.result = "Max turns reached"
        return SubagentResult(
            task_id=task_id,
            success=True,
            output="Max turns reached",
            messages=messages
        )

    def run_parallel(self, prompts: list[str]) -> list[SubagentResult]:
        task_ids = [self.spawn(prompt) for prompt in prompts]
        
        results = []
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_id = {
                executor.submit(self.run_task, tid): tid
                for tid in task_ids
            }
            
            for future in as_completed(future_to_id):
                tid = future_to_id[future]
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    results.append(SubagentResult(
                        task_id=tid,
                        success=False,
                        output=str(e),
                        messages=[]
                    ))
        
        return results

    def get_task(self, task_id: str) -> Optional[SubagentTask]:
        return self.tasks.get(task_id)

    def _save_checkpoint(self, task_id: str, messages: list[dict]):
        checkpoint_file = self._checkpoint_dir / f"{task_id}.json"
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump({
                "task_id": task_id,
                "messages": messages
            }, f, ensure_ascii=False, indent=2)

    def list_tasks(self) -> list[dict]:
        return [
            {
                "id": task.id,
                "prompt": task.prompt[:50] + "..." if len(task.prompt) > 50 else task.prompt,
                "status": task.status,
                "result": task.result[:100] if task.result else None
            }
            for task in self.tasks.values()
        ]
