"""Session checkpoint save/restore."""
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

from chip.context.tracker import ContextTracker


class CheckpointManager:
    def __init__(self, checkpoint_dir: Path):
        self.checkpoint_dir = checkpoint_dir
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

    def save(self, messages: list[dict], project_context: str = "", metadata: Optional[dict] = None) -> Path:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        checkpoint_file = self.checkpoint_dir / f"checkpoint_{timestamp}.json"

        data = {
            "version": "1.0",
            "timestamp": datetime.now().isoformat(),
            "messages": messages,
            "project_context": project_context,
            "metadata": metadata or {},
        }

        with open(checkpoint_file, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        return checkpoint_file

    def load(self, checkpoint_file: Path) -> Optional[dict[str, Any]]:
        try:
            with open(checkpoint_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return None

    def list_checkpoints(self) -> list[Path]:
        return sorted(self.checkpoint_dir.glob("checkpoint_*.json"), reverse=True)

    def get_latest(self) -> Optional[dict[str, Any]]:
        checkpoints = self.list_checkpoints()
        if checkpoints:
            return self.load(checkpoints[0])
        return None

    def generate_resume_prompt(self, messages: list[dict], project_context: str = "", tracker: Optional[ContextTracker] = None) -> str:
        summary_parts = []

        if project_context:
            summary_parts.append(f"PROJECT CONTEXT:\n{project_context}")

        user_messages = [m for m in messages if m.get("role") == "user"]
        assistant_messages = [m for m in messages if m.get("role") == "assistant"]
        tool_messages = [m for m in messages if m.get("role") == "tool"]

        summary_parts.append(f"SESSION STATS: {len(user_messages)} user messages, {len(assistant_messages)} assistant responses, {len(tool_messages)} tool calls")

        if tracker:
            summary_parts.append(f"CONTEXT USAGE: {tracker.usage_percent*100:.1f}% ({tracker.current_tokens}/{tracker.max_tokens} tokens)")

        recent_messages = messages[-10:] if len(messages) > 10 else messages
        summary_parts.append("RECENT CONVERSATION:")
        for msg in recent_messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            if content:
                preview = content[:200] + "..." if len(content) > 200 else content
                summary_parts.append(f"[{role}]: {preview}")

        return "\n\n".join(summary_parts)
