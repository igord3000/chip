"""CLI entry point with single-command setup and launch."""
import argparse
import subprocess
import sys
import os
from pathlib import Path


def check_ollama() -> bool:
    """Check if Ollama is installed and running."""
    try:
        result = subprocess.run(
            ["ollama", "list"],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def install_ollama():
    """Install Ollama."""
    print("Installing Ollama...")
    try:
        subprocess.run(
            "curl -fsSL https://ollama.ai/install.sh | sh",
            shell=True,
            check=True
        )
        print("Ollama installed successfully!")
        return True
    except subprocess.CalledProcessError:
        print("Failed to install Ollama. Please install manually:")
        print("  curl -fsSL https://ollama.ai/install.sh | sh")
        return False


def pull_model(model: str):
    """Pull an Ollama model."""
    print(f"Pulling model {model}...")
    try:
        subprocess.run(
            ["ollama", "pull", model],
            check=True
        )
        print(f"Model {model} ready!")
        return True
    except subprocess.CalledProcessError:
        print(f"Failed to pull model {model}")
        return False


def start_ollama():
    """Start Ollama server in background."""
    if check_ollama():
        print("Ollama is already running.")
        return True
    
    print("Starting Ollama server...")
    try:
        subprocess.Popen(
            ["ollama", "serve"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        import time
        time.sleep(2)
        return check_ollama()
    except Exception:
        return False


def setup(args=None):
    """Full setup: install Ollama, pull model, configure."""
    if args is None:
        parser = argparse.ArgumentParser(
            prog="chip setup",
            description="Setup Chip agent"
        )
        parser.add_argument("--model", default="qwen3:8b", help="Model to download (default: qwen3:8b)")
        parser.add_argument("--skip-ollama", action="store_true", help="Skip Ollama installation")
        args = parser.parse_args()
    
    print("=" * 60)
    print("Chip Agent Setup")
    print("=" * 60)
    
    if not args.skip_ollama:
        if not check_ollama():
            if not install_ollama():
                return False
        else:
            print("Ollama is already installed.")
    
    if not start_ollama():
        print("Warning: Could not start Ollama server.")
        print("You may need to start it manually: ollama serve")
    
    if not pull_model(args.model):
        return False
    
    config_path = Path(".env")
    if not config_path.exists():
        with open(config_path, "w") as f:
            f.write(f"""# Chip Configuration
LLM_BASE_URL=http://localhost:11434/v1
LLM_API_KEY=ollama
LLM_MODEL={args.model}
CONTEXT_MAX_TOKENS=32000
""")
        print(f"Created .env with model {args.model}")
    
    print("\n" + "=" * 60)
    print("Setup complete! Run your first task:")
    print(f'  chip run "Hello World"')
    print("=" * 60)
    return True


def run(args=None):
    """Run a task."""
    if args is None:
        parser = argparse.ArgumentParser(
            prog="chip run",
            description="Run a coding task"
        )
        parser.add_argument("task", nargs="*", help="Task to execute")
        parser.add_argument("--model", type=str, help="Override LLM model")
        parser.add_argument("--resume", type=str, help="Resume from checkpoint")
        parser.add_argument("--chat", action="store_true", help="Interactive chat mode")
        parser.add_argument("--max-turns", type=int, help="Max turns")
        parser.add_argument("--timeout", type=int, help="LLM timeout in seconds")
        args = parser.parse_args()
    
    from chip.agent import Agent
    from chip.config import load_config
    
    config = load_config()
    if args.model:
        config.llm.model = args.model
    if args.max_turns:
        config.max_turns = args.max_turns
    if args.timeout:
        config.llm.timeout = args.timeout
    
    agent = Agent(config)
    
    if args.chat:
        agent.chat()
    elif args.task:
        agent.run(" ".join(args.task), resume_from=args.resume)
    else:
        agent.chat()


def status():
    """Show status of Ollama and configuration."""
    print("Chip Status")
    print("=" * 40)
    
    ollama_ok = check_ollama()
    print(f"Ollama: {'Running' if ollama_ok else 'Not running'}")
    
    if ollama_ok:
        try:
            result = subprocess.run(
                ["ollama", "list"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.stdout:
                print("\nAvailable models:")
                for line in result.stdout.strip().split("\n")[1:]:
                    print(f"  {line}")
        except Exception:
            pass
    
    env_path = Path(".env")
    if env_path.exists():
        print(f"\n.env: {env_path.absolute()}")
    else:
        print("\n.env: Not found (using defaults)")


def sessions(args):
    """Manage sessions."""
    checkpoint_dir = Path(".chip")
    if not checkpoint_dir.exists():
        print("No sessions found.")
        return
    
    if args.action == "list":
        checkpoints = sorted(checkpoint_dir.glob("checkpoint_*.json"))
        if not checkpoints:
            print("No checkpoints found.")
            return
        print("Sessions:")
        for cp in checkpoints:
            print(f"  {cp.name}")
    
    elif args.action == "show" and args.id:
        cp_file = checkpoint_dir / args.id
        if not cp_file.exists():
            cp_file = checkpoint_dir / f"checkpoint_{args.id}.json"
        if cp_file.exists():
            import json
            with open(cp_file) as f:
                data = json.load(f)
            print(f"Session: {cp_file.name}")
            print(f"Timestamp: {data.get('timestamp', 'unknown')}")
            print(f"Messages: {len(data.get('messages', []))}")
        else:
            print(f"Session not found: {args.id}")
    
    elif args.action == "clean":
        import shutil
        shutil.rmtree(checkpoint_dir)
        print("Sessions cleaned.")


def main():
    parser = argparse.ArgumentParser(
        prog="chip",
        description="Minimal coding agent with context tracking"
    )
    subparsers = parser.add_subparsers(dest="command", help="Commands")
    
    subparsers.add_parser("setup", help="Install and configure Chip")
    
    run_parser = subparsers.add_parser("run", help="Run a coding task")
    run_parser.add_argument("task", nargs="*", help="Task to execute")
    run_parser.add_argument("--model", type=str, help="Override LLM model")
    run_parser.add_argument("--resume", type=str, help="Resume from checkpoint")
    run_parser.add_argument("--chat", action="store_true", help="Interactive chat mode")
    run_parser.add_argument("--max-turns", type=int, help="Max turns")
    run_parser.add_argument("--timeout", type=int, help="LLM timeout in seconds")
    
    subparsers.add_parser("status", help="Show system status")
    
    sessions_parser = subparsers.add_parser("sessions", help="Manage sessions")
    sessions_parser.add_argument("action", choices=["list", "show", "clean"])
    sessions_parser.add_argument("id", nargs="?")
    
    args = parser.parse_args()
    
    if args.command == "setup":
        setup(args)
    elif args.command == "run":
        run(args)
    elif args.command == "status":
        status()
    elif args.command == "sessions":
        sessions(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
