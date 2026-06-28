"""Main agent loop with context tracking and checkpointing."""
import json
from typing import Optional

from chip.config import AgentConfig, load_config
from chip.llm import LLMClient
from chip.tools import ToolRegistry
from chip.context.tracker import ContextTracker
from chip.context.checkpoint import CheckpointManager
from chip.ui.terminal import TerminalUI
from chip.subagent import SubagentManager


SYSTEM_PROMPT = """\
You are a coding agent with internet access. Your job is to help the user with programming tasks and research.

You have access to tools:
- `bash` — execute shell commands
- `read_file` — read file contents
- `write_file` — write to files
- `list_files` — list directory contents
- `subagent` — spawn a subagent for parallel tasks
- `web_fetch` — fetch content from URLs (web pages, APIs)
- `web_search` — search the web using DuckDuckGo
- `download` — download files from the internet

Workflow:
1. Plan what needs to be done.
2. Use tools to read files, run commands, write code, etc.
3. Use web_search to find information, documentation, solutions.
4. Use web_fetch to read web pages and documentation.
5. Use download to save files from the internet.
6. For complex tasks, use subagent to parallelize work.
7. After gathering enough information or completing the task, give your final answer in natural language.
8. To finish, reply with a regular message (no tool call).

Be concise. Explain what you're doing before each command."""


class Agent:
    def __init__(self, config: Optional[AgentConfig] = None):
        self.config = config or load_config()
        self.ui = TerminalUI()
        self.llm = LLMClient(self.config.llm)
        self.subagent_manager = SubagentManager(self.config)
        self.tools = ToolRegistry(
            bash_timeout=self.config.bash_timeout,
            subagent_manager=self.subagent_manager
        )
        self.tracker = ContextTracker(
            max_tokens=self.config.context.max_context_tokens,
            warning_threshold=self.config.context.warning_threshold,
            critical_threshold=self.config.context.critical_threshold,
        )
        self.checkpoint = CheckpointManager(self.config.checkpoint_dir)
        self.messages: list[dict] = []
        self.project_context: str = ""

    def run(self, user_message: str, resume_from: Optional[str] = None):
        if resume_from:
            self._resume_session(resume_from)

        self.ui.print_header(self.config.llm.model, self.tools.tool_names)

        if not self.messages:
            self.messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]
        else:
            self.messages.append({"role": "user", "content": user_message})

        self._run_loop()

    def _resume_session(self, checkpoint_path: str):
        from pathlib import Path
        data = self.checkpoint.load(Path(checkpoint_path))
        if data:
            self.messages = data.get("messages", [])
            self.project_context = data.get("project_context", "")
            self.ui.print_info(f"Resumed from checkpoint: {checkpoint_path}")
        else:
            self.ui.print_error(f"Failed to load checkpoint: {checkpoint_path}")

    def _run_loop(self):
        for turn in range(1, self.config.max_turns + 1):
            self.ui.print_turn(turn)

            try:
                response = self.llm.chat(self.messages, self.tools.to_openai_tools())
            except Exception as e:
                self.ui.print_error(f"LLM error: {e}")
                break

            if response.content:
                self.ui.print_assistant_message(response.content)

            if not response.tool_calls:
                self.ui.print_success("Agent finished")
                break

            for tool_call in response.tool_calls:
                func_name = tool_call["function"]["name"]
                try:
                    arguments = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError as e:
                    self.ui.print_error(f"Invalid JSON in tool arguments: {e}")
                    arguments = {}

                self.ui.print_tool_call(func_name, arguments)

                result = self.tools.call(func_name, arguments)
                self.ui.print_tool_result(result.output, result.success)

                self.messages.append({
                    "role": "assistant",
                    "content": response.content or None,
                    "tool_calls": [tool_call]
                })
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result.output if result.success else f"Error: {result.error}"
                })

            if self._update_context():
                break
        else:
            self.ui.print_warning(f"Max turns ({self.config.max_turns}) reached")

    def _update_context(self):
        tokens = self.tracker.update(self.messages)
        self.ui.print_context_meter(self.tracker)

        if self.tracker.is_critical:
            self._auto_checkpoint()
            self.ui.print_warning("Context limit reached. Agent stopped.")
            return True
        return False

    def _auto_checkpoint(self):
        path = self.checkpoint.save(
            self.messages,
            self.project_context,
            {"tokens_used": self.tracker.current_tokens}
        )
        self.ui.print_checkpoint_saved(str(path))

        resume_prompt = self.checkpoint.generate_resume_prompt(
            self.messages,
            self.project_context,
            self.tracker
        )
        checkpoint_file = self.config.checkpoint_dir / "latest_checkpoint.txt"
        with open(checkpoint_file, "w", encoding="utf-8") as f:
            f.write(resume_prompt)

        self.ui.print_info("Session auto-saved. Use --resume to continue.")

    def chat(self):
        """Interactive chat mode with context persistence."""
        self.ui.print_header(self.config.llm.model, self.tools.tool_names)
        self.ui.print_info("Interactive mode. Type 'exit' or 'quit' to stop.")
        self.ui.print_info("Type 'save' to save session, 'clear' to reset context.")
        print()
        
        # Load last session if exists
        self._load_last_session()
        
        while True:
            try:
                user_input = self.ui.get_user_input()
            except (EOFError, KeyboardInterrupt):
                print("\nGoodbye!")
                break
            
            if not user_input:
                continue
            
            if user_input.lower() in ('exit', 'quit', 'q'):
                self._save_session()
                print("Goodbye!")
                break
            
            if user_input.lower() == 'save':
                self._save_session()
                continue
            
            if user_input.lower() == 'clear':
                self.messages = [
                    {"role": "system", "content": SYSTEM_PROMPT}
                ]
                self.tracker = ContextTracker(
                    max_tokens=self.config.context.max_context_tokens,
                    warning_threshold=self.config.context.warning_threshold,
                    critical_threshold=self.config.context.critical_threshold,
                )
                print("Context cleared.")
                continue
            
            self._process_message(user_input)

    def _process_message(self, user_message: str):
        """Process a single message in chat mode."""
        if not self.messages:
            self.messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_message}
            ]
        else:
            self.messages.append({"role": "user", "content": user_message})
        
        for turn in range(1, self.config.max_turns + 1):
            try:
                response = self.llm.chat(self.messages, self.tools.to_openai_tools())
            except Exception as e:
                self.ui.print_error(f"LLM error: {e}")
                return
            
            if response.content:
                self.ui.print_assistant_message(response.content)
            
            if not response.tool_calls:
                self._update_context()
                return
            
            for tool_call in response.tool_calls:
                func_name = tool_call["function"]["name"]
                try:
                    arguments = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}
                
                self.ui.print_tool_call(func_name, arguments)
                result = self.tools.call(func_name, arguments)
                self.ui.print_tool_result(result.output, result.success)
                
                self.messages.append({
                    "role": "assistant",
                    "content": response.content or None,
                    "tool_calls": [tool_call]
                })
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result.output if result.success else f"Error: {result.error}"
                })
            
            if self._update_context():
                return

    def _save_session(self):
        """Save current session."""
        if self.messages and len(self.messages) > 1:
            path = self.checkpoint.save(
                self.messages,
                self.project_context,
                {"tokens_used": self.tracker.current_tokens}
            )
            self.ui.print_info(f"Session saved: {path}")
            
            # Also save as last session
            last_session = self.config.checkpoint_dir / "last_session.json"
            with open(last_session, "w", encoding="utf-8") as f:
                json.dump({
                    "messages": self.messages,
                    "project_context": self.project_context
                }, f, ensure_ascii=False, indent=2)

    def _load_last_session(self):
        """Load last session if exists."""
        last_session = self.config.checkpoint_dir / "last_session.json"
        if last_session.exists():
            try:
                with open(last_session, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.messages = data.get("messages", [])
                self.project_context = data.get("project_context", "")
                self.ui.print_info(f"Loaded previous session ({len(self.messages)} messages)")
            except Exception:
                pass
