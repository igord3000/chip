"""Error recovery and retry logic."""
import time
from typing import Callable, Any
from functools import wraps


class RetryError(Exception):
    """Raised when all retries exhausted."""
    def __init__(self, message: str, last_error: Exception):
        super().__init__(message)
        self.last_error = last_error


def with_retry(
    func: Callable,
    max_retries: int = 3,
    delay: float = 1.0,
    backoff: float = 2.0,
    exceptions: tuple = (Exception,)
) -> Callable:
    """Decorator for retry logic with exponential backoff."""
    @wraps(func)
    def wrapper(*args, **kwargs) -> Any:
        last_exception = None
        
        for attempt in range(max_retries):
            try:
                return func(*args, **kwargs)
            except exceptions as e:
                last_exception = e
                if attempt < max_retries - 1:
                    wait_time = delay * (backoff ** attempt)
                    time.sleep(wait_time)
        
        raise RetryError(
            f"Failed after {max_retries} attempts",
            last_exception
        )
    
    return wrapper


class ErrorRecovery:
    """Handles errors and suggests recovery actions."""
    
    RECOVERY_SUGGESTIONS = {
        "ConnectionError": [
            "Check if the server is running",
            "Verify the URL is correct",
            "Check your internet connection"
        ],
        "TimeoutError": [
            "Try a simpler query",
            "Increase timeout in config",
            "Check server load"
        ],
        "RateLimitError": [
            "Wait a few seconds and retry",
            "Reduce request frequency",
            "Use a different API key"
        ],
        "AuthenticationError": [
            "Check your API key",
            "Verify the key has correct permissions",
            "Generate a new key"
        ]
    }
    
    @staticmethod
    def suggest_recovery(error: Exception) -> list[str]:
        """Suggest recovery actions based on error type."""
        error_type = type(error).__name__
        
        # Check exact match
        if error_type in ErrorRecovery.RECOVERY_SUGGESTIONS:
            return ErrorRecovery.RECOVERY_SUGGESTIONS[error_type]
        
        # Check partial matches
        error_str = str(error).lower()
        for keyword, suggestions in ErrorRecovery.RECOVERY_SUGGESTIONS.items():
            if keyword.lower() in error_str:
                return suggestions
        
        return ["Check the error message and try again"]
