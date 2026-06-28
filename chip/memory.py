"""Long-term memory for Chip agent."""
import json
from pathlib import Path
from typing import Optional
from datetime import datetime


class Memory:
    """Persistent memory across sessions."""
    
    def __init__(self, memory_dir: Path):
        self.memory_dir = memory_dir
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.facts_file = memory_dir / "facts.json"
        self.context_file = memory_dir / "context.json"
        
        self.facts = self._load(self.facts_file) or []
        self.context = self._load(self.context_file) or {}
    
    def remember(self, fact: str, category: str = "general"):
        """Store a fact in memory."""
        self.facts.append({
            "fact": fact,
            "category": category,
            "timestamp": datetime.now().isoformat()
        })
        self._save(self.facts_file, self.facts)
    
    def recall(self, query: str) -> list[str]:
        """Recall relevant facts."""
        query_lower = query.lower()
        relevant = []
        for item in self.facts:
            if query_lower in item["fact"].lower():
                relevant.append(item["fact"])
        return relevant[-5:]  # Last 5 relevant facts
    
    def set_context(self, key: str, value: str):
        """Set context (e.g., user preferences, project info)."""
        self.context[key] = value
        self._save(self.context_file, self.context)
    
    def get_context(self, key: str) -> Optional[str]:
        """Get context value."""
        return self.context.get(key)
    
    def get_all_context(self) -> dict:
        """Get all context."""
        return self.context.copy()
    
    def _load(self, filepath: Path) -> Optional[list | dict]:
        if filepath.exists():
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return None
        return None
    
    def _save(self, filepath: Path, data: list | dict):
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
