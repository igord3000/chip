"""Chip CLI — single command interface."""
import argparse
import subprocess
import sys
import json
from pathlib import Path


def ensure_ollama():
    """Ensure Ollama is running, start if needed."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return True
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    
    print("Starting Ollama...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        import time
        time.sleep(2)
        return True
    except Exception:
        print("Cannot start Ollama. Run: ollama serve")
        return False


def cmd_gui(args):
    """Launch Textual GUI."""
    from chip.ui.textual_app import ChipApp
    app = ChipApp(model=args.model)
    app.run()


def cmd_chat(args):
    """Launch CLI chat."""
    from chip.agent import Agent
    from chip.config import load_config
    
    config = load_config()
    if args.model:
        config.llm.model = args.model
    
    agent = Agent(config)
    
    if args.task:
        agent.run(" ".join(args.task), resume_from=args.resume)
    else:
        agent.chat()


def cmd_setup(args):
    """Setup Chip."""
    print("=" * 50)
    print("  Chip Agent Setup")
    print("=" * 50)
    
    # Install Ollama if needed
    try:
        subprocess.run(["ollama", "--version"], capture_output=True, check=True)
        print("✓ Ollama installed")
    except Exception:
        print("Installing Ollama...")
        subprocess.run("curl -fsSL https://ollama.ai/install.sh | sh", shell=True)
    
    # Start Ollama
    ensure_ollama()
    print("✓ Ollama running")
    
    # Pull model
    model = args.model
    print(f"Pulling {model}...")
    subprocess.run(["ollama", "pull", model])
    print(f"✓ Model {model} ready")
    
    # Create config
    config_path = Path.home() / ".chip" / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    if not config_path.exists():
        with open(config_path, "w") as f:
            json.dump({"model": model}, f)
    
    print("\n✓ Setup complete!")
    print(f"\nRun: chip")


def cmd_status(args):
    """Show status."""
    print("Chip Status")
    print("-" * 40)
    
    try:
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True, timeout=5)
        print("Ollama: Running")
        if result.stdout:
            for line in result.stdout.strip().split("\n")[1:]:
                print(f"  {line}")
    except Exception:
        print("Ollama: Not running")


def cmd_restart():
    """Restart Ollama."""
    from chip.ollama_service import restart_ollama
    restart_ollama()


def cmd_reload():
    """Reload Chip - restart the current process."""
    import os
    import sys
    print("Перезапуск Chip...")
    os.execv(sys.executable, [sys.executable] + sys.argv)


def cmd_providers():
    """List available providers."""
    from chip.providers import ProviderManager
    
    manager = ProviderManager()
    
    print("Доступные провайдеры:")
    print("-" * 50)
    
    for key, provider in manager.list_providers():
        status = "✓" if provider.api_key or provider.type.value == "ollama" else "✗ нет ключа"
        print(f"  {key:15} {provider.name:25} [{status}]")
        if provider.api_key or provider.type.value == "ollama":
            print(f"  {'':15} URL: {provider.base_url}")
            print(f"  {'':15} Модели: {', '.join(provider.models[:3])}...")


def cmd_sessions(args):
    """Manage sessions."""
    checkpoint_dir = Path.home() / ".chip" / "sessions"
    
    if args.action == "list":
        if not checkpoint_dir.exists():
            print("No sessions.")
            return
        for f in sorted(checkpoint_dir.glob("*.json"))[-5:]:
            print(f"  {f.stem}")
    
    elif args.action == "clean":
        import shutil
        if checkpoint_dir.exists():
            shutil.rmtree(checkpoint_dir)
        print("Sessions cleaned.")


def main():
    parser = argparse.ArgumentParser(
        prog="chip",
        description="AI coding agent",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  chip                        # Launch GUI
  chip -c                     # CLI chat mode
  chip -c "Hello"             # CLI with task
  chip -c -m qwen3:8b         # CLI with model
  chip -c --resume            # Resume last session
  chip -s                     # Setup
  chip --status               # Show status
"""
    )
    
    parser.add_argument("-c", "--chat", action="store_true", help="CLI chat mode")
    parser.add_argument("-g", "--gui", action="store_true", help="Launch GUI (default)")
    parser.add_argument("-m", "--model", type=str, help="LLM model")
    parser.add_argument("-r", "--resume", action="store_true", help="Resume last session")
    parser.add_argument("-s", "--setup", action="store_true", help="Setup Chip")
    parser.add_argument("--status", action="store_true", help="Show status")
    parser.add_argument("--restart", action="store_true", help="Restart Ollama")
    parser.add_argument("--reload", action="store_true", help="Reload Chip (restart GUI)")
    parser.add_argument("--providers", action="store_true", help="List providers")
    parser.add_argument("--sessions", nargs="?", const="list", help="Manage sessions")
    parser.add_argument("task", nargs="*", help="Task to execute")
    
    args = parser.parse_args()
    
    # No args = GUI
    if not any([args.chat, args.setup, args.status, args.sessions, args.task, args.restart, args.providers, args.reload]):
        args.gui = True
    
    if args.setup:
        cmd_setup(args)
    elif args.restart:
        cmd_restart()
    elif args.reload:
        cmd_reload()
    elif args.providers:
        cmd_providers()
    elif args.status:
        cmd_status(args)
    elif args.sessions:
        args.action = args.sessions
        cmd_sessions(args)
    elif args.chat:
        ensure_ollama()
        cmd_chat(args)
    else:
        ensure_ollama()
        cmd_gui(args)


if __name__ == "__main__":
    main()
