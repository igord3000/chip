"""Ollama service management."""
import subprocess
import time
import sys


def check_ollama() -> bool:
    """Check if Ollama is running."""
    try:
        result = subprocess.run(
            ["curl", "-s", "http://localhost:11434/api/tags"],
            capture_output=True, text=True, timeout=3
        )
        return result.returncode == 0 and '"models"' in result.stdout
    except Exception:
        return False


def start_ollama() -> bool:
    """Start Ollama server."""
    if check_ollama():
        return True
    
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            start_new_session=True
        )
        time.sleep(3)
        return check_ollama()
    except Exception:
        return False


def stop_ollama() -> bool:
    """Stop Ollama server."""
    try:
        subprocess.run(["pkill", "-f", "ollama serve"], capture_output=True)
        time.sleep(1)
        return not check_ollama()
    except Exception:
        return False


def restart_ollama() -> bool:
    """Restart Ollama server."""
    print("Stopping Ollama...")
    stop_ollama()
    print("Starting Ollama...")
    if start_ollama():
        print("✓ Ollama is running")
        return True
    else:
        print("✗ Failed to start Ollama")
        print("Try: sudo systemctl restart ollama")
        return False


def ensure_ollama() -> bool:
    """Ensure Ollama is running, start if needed."""
    if check_ollama():
        return True
    
    print("Starting Ollama...")
    return start_ollama()
