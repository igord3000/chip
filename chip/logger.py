"""Logging system for Chip agent."""
import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Optional


class ChipLogger:
    """Centralized logging with file output."""
    
    def __init__(self, log_dir: Optional[Path] = None):
        self.log_dir = log_dir or Path.home() / ".chip" / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        self._log_file = self.log_dir / f"chip_{datetime.now().strftime('%Y%m%d')}.log"
        self._errors_file = self.log_dir / "errors.jsonl"
        
        # Setup standard logger
        self.logger = logging.getLogger("chip")
        self.logger.setLevel(logging.DEBUG)
        
        # File handler
        fh = logging.FileHandler(self._log_file, encoding="utf-8")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        self.logger.addHandler(fh)
    
    def debug(self, msg: str, **kwargs):
        self.logger.debug(msg, **kwargs)
    
    def info(self, msg: str, **kwargs):
        self.logger.info(msg, **kwargs)
    
    def warning(self, msg: str, **kwargs):
        self.logger.warning(msg, **kwargs)
    
    def error(self, msg: str, error: Optional[Exception] = None, **kwargs):
        self.logger.error(msg, **kwargs)
        
        # Save error to JSONL for tracking
        error_entry = {
            "timestamp": datetime.now().isoformat(),
            "message": msg,
            "error_type": type(error).__name__ if error else None,
            "error_msg": str(error) if error else None,
            "resolved": False
        }
        
        with open(self._errors_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(error_entry, ensure_ascii=False) + "\n")
    
    def get_errors(self) -> list[dict]:
        """Get all logged errors."""
        errors = []
        if self._errors_file.exists():
            with open(self._errors_file, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        errors.append(json.loads(line))
        return errors
    
    def get_new_errors(self, since: Optional[str] = None) -> list[dict]:
        """Get errors since timestamp."""
        errors = self.get_errors()
        if since:
            errors = [e for e in errors if e["timestamp"] > since]
        return errors
    
    def mark_resolved(self, timestamp: str):
        """Mark an error as resolved."""
        errors = self.get_errors()
        for e in errors:
            if e["timestamp"] == timestamp:
                e["resolved"] = True
        
        with open(self._errors_file, "w", encoding="utf-8") as f:
            for e in errors:
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
    
    def get_log_file(self) -> Path:
        return self._log_file


# Global logger instance
_logger: Optional[ChipLogger] = None


def get_logger() -> ChipLogger:
    global _logger
    if _logger is None:
        _logger = ChipLogger()
    return _logger
