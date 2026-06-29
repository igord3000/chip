"""Response and context caching for Chip agent."""
import json
import hashlib
from pathlib import Path
from typing import Optional
from datetime import datetime, timedelta


class ResponseCache:
    """Cache LLM responses to save tokens."""
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.ttl = timedelta(hours=ttl_hours)
        self._memory_cache: dict[str, dict] = {}
    
    def _make_key(self, messages: list[dict]) -> str:
        """Create cache key from messages."""
        content = json.dumps(messages, sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def get(self, messages: list[dict]) -> Optional[str]:
        """Get cached response if exists and not expired."""
        # Don't cache weather/current data queries
        for msg in messages:
            if msg.get("role") == "user":
                content = msg.get("content", "").lower()
                if any(w in content for w in ['погод', 'курс', 'цен', 'акци']):
                    return None  # Don't use cache for current data
        
        key = self._make_key(messages)
        
        # Check memory cache first
        if key in self._memory_cache:
            entry = self._memory_cache[key]
            timestamp = entry["timestamp"]
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            if datetime.now() - timestamp < self.ttl:
                return entry["response"]
            del self._memory_cache[key]
        
        # Check disk cache
        cache_file = self.cache_dir / f"{key}.json"
        if cache_file.exists():
            try:
                with open(cache_file, "r", encoding="utf-8") as f:
                    entry = json.load(f)
                timestamp = datetime.fromisoformat(entry["timestamp"])
                if datetime.now() - timestamp < self.ttl:
                    self._memory_cache[key] = entry
                    return entry["response"]
                cache_file.unlink()
            except Exception:
                pass
        
        return None
    
    def set(self, messages: list[dict], response: str):
        """Cache a response."""
        key = self._make_key(messages)
        entry = {
            "timestamp": datetime.now().isoformat(),
            "response": response,
            "token_count": len(response.split())
        }
        
        # Save to memory
        self._memory_cache[key] = entry
        
        # Save to disk
        cache_file = self.cache_dir / f"{key}.json"
        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(entry, f, ensure_ascii=False)
        except Exception:
            pass
    
    def clear(self):
        """Clear all caches."""
        self._memory_cache.clear()
        for f in self.cache_dir.glob("*.json"):
            f.unlink()
    
    def stats(self) -> dict:
        """Get cache statistics."""
        disk_files = list(self.cache_dir.glob("*.json"))
        total_tokens = 0
        for f in disk_files:
            try:
                with open(f) as fh:
                    data = json.load(fh)
                total_tokens += data.get("token_count", 0)
            except Exception:
                pass
        
        return {
            "memory_entries": len(self._memory_cache),
            "disk_entries": len(disk_files),
            "estimated_tokens_saved": total_tokens
        }


class SemanticCache:
    """Cache based on semantic similarity (simple keyword matching)."""
    
    def __init__(self):
        self._cache: list[dict] = []
    
    def _extract_keywords(self, text: str) -> set[str]:
        """Extract keywords from text."""
        words = set()
        for word in text.lower().split():
            if len(word) > 3:
                words.add(word)
        return words
    
    def _similarity(self, a: str, b: str) -> float:
        """Simple keyword-based similarity."""
        kw_a = self._extract_keywords(a)
        kw_b = self._extract_keywords(b)
        if not kw_a or not kw_b:
            return 0.0
        intersection = kw_a & kw_b
        union = kw_a | kw_b
        return len(intersection) / len(union)
    
    def get(self, query: str, threshold: float = 0.4) -> Optional[str]:
        """Find similar cached response."""
        # Don't use cache for weather/current data queries
        if any(w in query.lower() for w in ['погод', 'курс', 'цен', 'акци']):
            return None
        
        best_match = None
        best_score = 0.0
        
        for entry in self._cache:
            score = self._similarity(query, entry["query"])
            if score > best_score and score >= threshold:
                best_score = score
                best_match = entry["response"]
        
        return best_match
    
    def set(self, query: str, response: str):
        """Cache query-response pair."""
        self._cache.append({
            "query": query,
            "response": response,
            "timestamp": datetime.now().isoformat()
        })
        
        # Keep only last 100 entries
        if len(self._cache) > 100:
            self._cache = self._cache[-100:]
    
    def clear(self):
        self._cache.clear()
