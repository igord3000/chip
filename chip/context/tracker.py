"""Context window tracking with tiktoken."""
from typing import Optional

try:
    import tiktoken
    HAS_TIKTOKEN = True
except ImportError:
    HAS_TIKTOKEN = False


class ContextTracker:
    def __init__(self, max_tokens: int = 32000, warning_threshold: float = 0.70, critical_threshold: float = 0.90):
        self.max_tokens = max_tokens
        self.warning_threshold = warning_threshold
        self.critical_threshold = critical_threshold
        self._encoder = tiktoken.get_encoding("cl100k_base") if HAS_TIKTOKEN else None
        self._token_counts: list[int] = []
        self._total_tokens: int = 0

    def count_tokens(self, text: str) -> int:
        if self._encoder:
            return len(self._encoder.encode(text))
        return len(text) // 4

    def count_message_tokens(self, messages: list[dict]) -> int:
        total = 0
        for msg in messages:
            content = msg.get("content") or ""
            total += self.count_tokens(str(content))
            if "tool_calls" in msg and msg["tool_calls"]:
                total += 20
                for tc in msg["tool_calls"]:
                    func = tc.get("function", {})
                    total += self.count_tokens(func.get("name", ""))
                    total += self.count_tokens(func.get("arguments", ""))
            total += 4
        return total

    def update(self, messages: list[dict]) -> int:
        tokens = self.count_message_tokens(messages)
        self._total_tokens = tokens
        self._token_counts.append(tokens)
        return tokens

    @property
    def current_tokens(self) -> int:
        return self._total_tokens

    @property
    def usage_percent(self) -> float:
        return self._total_tokens / self.max_tokens if self.max_tokens > 0 else 0

    @property
    def remaining_tokens(self) -> int:
        return max(0, self.max_tokens - self._total_tokens)

    @property
    def is_warning(self) -> bool:
        return self.usage_percent >= self.warning_threshold

    @property
    def is_critical(self) -> bool:
        return self.usage_percent >= self.critical_threshold

    @property
    def status(self) -> str:
        if self.is_critical:
            return "critical"
        if self.is_warning:
            return "warning"
        return "ok"
