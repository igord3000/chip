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
from chip.memory import Memory
from chip.recovery import ErrorRecovery
from chip.router import QueryRouter, QueryType
from chip.logger import get_logger


SYSTEM_PROMPT = """\
Ты — Chip, умный AI-ассистент с доступом к инструментам.

ИНСТРУМЕНТЫ:
- bash — выполнять команды
- read_file — читать файлы
- write_file — записывать файлы
- list_files — список файлов
- web_search — искать в интернете
- web_fetch — читать страницы по URL
- subagent — выполнять подзадачи

ВАЖНЫЕ ПРАВИЛА:

1. ОПРЕДЕЛИ ТИП ЗАПРОСА:
   - Текущие данные (погода, курсы) → web_search → web_fetch → ответ
   - Знания (что такое Python) → ответь из знаний
   - Код → используй инструменты
   - Простой вопрос → ответь сразу

2. ПОСЛЕ ВЫЗОВА ИНСТРУМЕНТА:
   - ВСЕГДА давай ответ на основе результата инструмента
   - Не просто показывай результат — ОБОБЩИ его
   - Будь конкретен: цифры, факты, ссылки

3. ПРИ ПОИСКЕ:
   - web_search → web_fetch → ОБОБЩИ результат
   - Не показывай просто ссылки — покажи ДАННЫЕ

4. ОТВЕЧАЙ:
   - На русском языке
   - Кратко и по существу
   - С конкретными фактами"""


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
        self.memory = Memory(self.config.checkpoint_dir / "memory")
        self.recovery = ErrorRecovery()
        self.router = QueryRouter()
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
        """Interactive chat mode - like ChatGPT/Claude interface."""
        from chip.ui.chat import ChatUI
        
        chat_ui = ChatUI(
            model=self.config.llm.model,
            tools=self.tools.tool_names,
            checkpoint_dir=self.config.checkpoint_dir
        )
        
        chat_ui.print_welcome()
        
        # Start fresh - don't auto-load old sessions
        # Use /resume to load previous session
        chat_ui.print_info("Starting fresh session. Use /resume to load previous.")
        
        while True:
            user_input = chat_ui.get_input()
            
            if not user_input:
                continue
            
            # Handle commands
            if user_input.startswith("/"):
                cmd = user_input.lower().strip()
                if cmd in ("/exit", "/quit", "/q"):
                    self._save_session()
                    chat_ui.print_info("Session saved. Goodbye!")
                    break
                elif cmd == "/save":
                    self._save_session()
                    chat_ui.print_session_saved("saved")
                    continue
                elif cmd == "/clear":
                    self.messages = [{"role": "system", "content": SYSTEM_PROMPT}]
                    self.tracker = ContextTracker(
                        max_tokens=self.config.context.max_context_tokens,
                        warning_threshold=self.config.context.warning_threshold,
                        critical_threshold=self.config.context.critical_threshold,
                    )
                    chat_ui.print_info("Context cleared.")
                    continue
                elif cmd == "/sessions":
                    self._show_sessions(chat_ui)
                    continue
                elif cmd == "/history":
                    self._show_history(chat_ui)
                    continue
                elif cmd == "/resume":
                    self._load_last_session()
                    if self.messages:
                        chat_ui.print_info(f"Loaded session ({len(self.messages)} messages)")
                    else:
                        chat_ui.print_info("No previous session found.")
                    continue
                elif cmd.startswith("/remember"):
                    fact = user_input[9:].strip()
                    if fact:
                        self.memory.remember(fact)
                        chat_ui.print_info(f"Remembered: {fact}")
                    else:
                        chat_ui.print_info("Usage: /remember <fact>")
                    continue
                elif cmd.startswith("/recall"):
                    query = user_input[7:].strip()
                    if query:
                        facts = self.memory.recall(query)
                        if facts:
                            chat_ui.print_info("Memories:")
                            for f in facts:
                                chat_ui.print_info(f"  • {f}")
                        else:
                            chat_ui.print_info("No memories found.")
                    else:
                        chat_ui.print_info("Usage: /recall <query>")
                    continue
                elif cmd == "/help":
                    self._show_help(chat_ui)
                    continue
                else:
                    chat_ui.print_info("Unknown command. Type /help")
                    continue
            
            # Process message
            chat_ui.print_user_message(user_input)
            self._process_message_with_ui(user_input, chat_ui)

    def _process_message_with_ui(self, user_message: str, chat_ui):
        """Process message with chat UI."""
        log = get_logger()
        from chip.history import QueryHistory
        from chip.orchestrator import Orchestrator
        
        history = QueryHistory()
        orchestrator = Orchestrator(self.config)
        
        # Route query and get hint
        query_type = self.router.route(user_message)
        hint = self.router.get_prompt_hint(query_type)
        
        log.info(f"Query: {user_message}")
        log.info(f"Query type: {query_type.value}")
        
        # Create history entry
        entry = history.create_entry(user_message, query_type.value)
        
        # Use orchestrator for execution
        start_time = __import__('time').time()
        
        if chat_ui:
            chat_ui.print_info(f"Тип: {query_type.value}")
        
        result = orchestrator.execute(user_message, callback=lambda msg: chat_ui.print_info(msg) if chat_ui else None)
        
        duration_ms = int((__import__('time').time() - start_time) * 1000)
        
        # Update history
        history.update_entry(
            entry.id,
            response=result.answer,
            success=result.success,
            duration_ms=duration_ms
        )
        
        # Show answer
        if chat_ui:
            chat_ui.print_assistant_message(result.answer)
        
        # Update messages for context
        self.messages.append({"role": "user", "content": user_message})
        self.messages.append({"role": "assistant", "content": result.answer})
        
        log.info(f"Response: {result.answer[:200]}...")
        log.info(f"Duration: {duration_ms}ms")
                suggestions = self.recovery.suggest_recovery(e)
                chat_ui.print_error(f"LLM error: {e}")
                chat_ui.print_info("Suggestions:")
                for s in suggestions:
                    chat_ui.print_info(f"  • {s}")
                return
            
            log.info(f"LLM response: content={response.content[:100] if response.content else 'None'}, tool_calls={len(response.tool_calls)}")
            
            if response.content:
                chat_ui.print_assistant_message(response.content)
            
            if not response.tool_calls:
                log.info("No tool calls - returning response")
                tokens = self.tracker.update(self.messages)
                chat_ui.print_token_bar(self.tracker)
                return
            
            for tool_call in response.tool_calls:
                func_name = tool_call["function"]["name"]
                try:
                    arguments = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}
                
                chat_ui.print_tool_call(func_name, arguments)
                self.log_activity(f"Вызов: {func_name}", "yellow")
                
                result = self.tools.call(func_name, arguments)
                chat_ui.print_tool_result(result.output, result.success)
                
                self.log_activity(f"Результат: {result.output[:150]}...", "green" if result.success else "red")
                
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
                
                # AUTO-PIPELINE: After web_search, automatically fetch first URL
                if func_name == "web_search" and result.success:
                    first_url = self._extract_first_url(result.output)
                    if first_url:
                        chat_ui.print_info(f"Fetching: {first_url}")
                        fetch_result = self.tools.call("web_fetch", {"url": first_url, "format": "text"})
                        
                        if fetch_result.success:
                            self.messages.append({
                                "role": "assistant",
                                "content": None,
                                "tool_calls": [{
                                    "id": f"auto_fetch_{tool_call['id']}",
                                    "type": "function",
                                    "function": {
                                        "name": "web_fetch",
                                        "arguments": json.dumps({"url": first_url, "format": "text"})
                                    }
                                }]
                            })
                            self.messages.append({
                                "role": "tool",
                                "tool_call_id": f"auto_fetch_{tool_call['id']}",
                                "content": fetch_result.output[:1500] if len(fetch_result.output) > 1500 else fetch_result.output
                            })
                            self.log_activity(f"  → Загружено: {len(fetch_result.output)} символов (обрезано)", "green")
                            chat_ui.print_tool_result(fetch_result.output[:200], True)
            
            tokens = self.tracker.update(self.messages)
            if self.tracker.is_critical:
                self._auto_checkpoint()
                chat_ui.print_error("Context limit reached!")
                return

    def _show_sessions(self, chat_ui):
        """Show available sessions."""
        checkpoints = sorted(self.checkpoint_dir.glob("checkpoint_*.json"))
        if not checkpoints:
            chat_ui.print_info("No saved sessions.")
            return
        chat_ui.print_info("Saved sessions:")
        for cp in checkpoints[-5:]:
            chat_ui.print_info(f"  {cp.name}")

    def _show_history(self, chat_ui):
        """Show query history."""
        from chip.history import QueryHistory
        history = QueryHistory()
        recent = history.get_recent(10)
        
        if not recent:
            chat_ui.print_info("No query history.")
            return
        
        chat_ui.print_info("Last queries:")
        for entry in recent:
            status = "✓" if entry.success else "✗"
            chat_ui.print_info(f"  {status} [{entry.query_type}] {entry.query[:50]}")

    def _extract_first_url(self, text: str) -> Optional[str]:
        """Extract first URL from search results."""
        import re
        urls = re.findall(r'https?://[^\s\)]+', text)
        if urls:
            return urls[0]
        return None

    def _show_help(self, chat_ui):
        """Show help."""
        help_text = """
Commands:
  /exit, /quit  - Save and exit
  /save         - Save current session
  /resume       - Load previous session
  /clear        - Clear context
  /sessions     - List saved sessions
  /history      - Show query history
  /remember <fact> - Remember something
  /recall <query>  - Recall memories
  /help         - Show this help
"""
        chat_ui.print_info(help_text)

    def _save_session(self):
        """Save current session."""
        if self.messages and len(self.messages) > 1:
            path = self.checkpoint.save(
                self.messages,
                self.project_context,
                {"tokens_used": self.tracker.current_tokens}
            )
            
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
            except Exception:
                pass
