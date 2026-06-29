"""Query history - tracks all user queries for analysis."""
import json
from datetime import datetime
from pathlib import Path
from typing import Optional
from dataclasses import dataclass, asdict


@dataclass
class QueryEntry:
    id: str
    query: str
    query_type: str
    timestamp: str
    response: str = ""
    tools_used: list[str] = None
    subagents_used: bool = False
    duration_ms: int = 0
    success: bool = True
    error: str = ""
    
    def to_dict(self) -> dict:
        return asdict(self)


class QueryHistory:
    """Tracks all user queries for analysis."""
    
    def __init__(self, history_dir: Optional[Path] = None):
        self.history_dir = history_dir or Path.home() / ".chip" / "history"
        self.history_dir.mkdir(parents=True, exist_ok=True)
        self.history_file = self.history_dir / "queries.jsonl"
        self._entries: list[QueryEntry] = []
        self._load()
    
    def _load(self):
        """Load history from file."""
        if self.history_file.exists():
            try:
                with open(self.history_file, "r", encoding="utf-8") as f:
                    for line in f:
                        if line.strip():
                            data = json.loads(line)
                            self._entries.append(QueryEntry(**data))
            except Exception:
                pass
    
    def add(self, entry: QueryEntry):
        """Add query entry to history."""
        self._entries.append(entry)
        
        # Append to file
        with open(self.history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
    
    def create_entry(self, query: str, query_type: str) -> QueryEntry:
        """Create a new query entry."""
        entry = QueryEntry(
            id=str(len(self._entries) + 1),
            query=query,
            query_type=query_type,
            timestamp=datetime.now().isoformat()
        )
        self._entries.append(entry)
        return entry
    
    def update_entry(self, entry_id: str, **kwargs):
        """Update an existing entry."""
        for entry in self._entries:
            if entry.id == entry_id:
                for key, value in kwargs.items():
                    if hasattr(entry, key):
                        setattr(entry, key, value)
                break
        
        # Rewrite file
        self._save()
    
    def _save(self):
        """Save all entries to file."""
        with open(self.history_file, "w", encoding="utf-8") as f:
            for entry in self._entries:
                f.write(json.dumps(entry.to_dict(), ensure_ascii=False) + "\n")
    
    def get_recent(self, n: int = 10) -> list[QueryEntry]:
        """Get last N queries."""
        return self._entries[-n:]
    
    def get_stats(self) -> dict:
        """Get statistics about queries."""
        if not self._entries:
            return {"total": 0}
        
        types = {}
        for entry in self._entries:
            t = entry.query_type
            types[t] = types.get(t, 0) + 1
        
        return {
            "total": len(self._entries),
            "types": types,
            "avg_duration_ms": sum(e.duration_ms for e in self._entries) / len(self._entries),
            "success_rate": sum(1 for e in self._entries if e.success) / len(self._entries)
        }
    
    def clear(self):
        """Clear all history."""
        self._entries.clear()
        if self.history_file.exists():
            self.history_file.unlink()
