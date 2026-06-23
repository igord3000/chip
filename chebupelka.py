"""Minimal coding agent loop — one tool: bash."""
import json, sys, subprocess
import requests


LLM_BASE_URL = "http://ip:port/v1"
LLM_API_KEY = "..."
LLM_MODEL = "..."
LLM_HEADERS = {"Content-Type": "application/json", "Authorization": f"Bearer {LLM_API_KEY}"}
MAX_TURNS = 1000

SYSTEM_PROMPT = """\
You are a coding agent. Your job is to help the user with programming tasks.

You have access to ONE tool: `bash` — which executes shell commands and returns stdout/stderr.

Workflow:
1. Plan what needs to be done.
2. Use `bash` to read files, run commands, write code, etc.
3. After gathering enough information or completing the task, give your final answer in natural language.
4. To finish, reply with a regular message (no tool call).

Be concise. Explain what you're doing before each command."""

LLM_TOOLS = [
    {"type": "function",
     "function": {"name": "bash",
                  "description": "Execute a shell command and return the output.",
                  "parameters": {"type": "object",
                                 "properties": {
                                     "command": {"type": "string", "description": "The bash command to execute."}
                                 },
                                 "required": ["command"]}
                 }
            }]


def run_bash(command: str) -> str:
    try:
        command_result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=120)
        out = command_result.stdout + (f"\nSTDERR:\n{command_result.stderr}" if command_result.stderr else "")
        return f"Exit code: {command_result.returncode}\n{out}"
    except subprocess.TimeoutExpired:
        return "Error: command timed out after 120s"


def call_tool(name: str, arguments: dict) -> str:
    func = {"bash": run_bash}.get(name)
    if not func:
        return f"Error: unknown tool '{name}'"
    try:
        return func(**arguments)
    except Exception as e:
        return f"Error calling {name}: {e}"


def call_llm(messages):
    payload = {"model": LLM_MODEL, "messages": messages, "tools": LLM_TOOLS, "tool_choice": "auto",
               "temperature": 0.1, "max_tokens": 4096}
    llm_http_response = requests.post(f"{LLM_BASE_URL}/chat/completions", json=payload, headers=LLM_HEADERS)
    llm_http_response.raise_for_status()
    msg = llm_http_response.json()["choices"][0]["message"]
    content = (msg.get("content") or "").strip()
    tool_calls = msg.get("tool_calls") or []
    return content, tool_calls


def agent_loop(user_message: str) -> None:
    messages: list[dict[str, object]] = [
        {"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user_message}
    ]
    for turn in range(1, MAX_TURNS + 1):
        print(f"\n{'='*60}\n🔄 Turn {turn}\n{'='*60}")
        content, tool_calls = call_llm(messages)
        if content:
            print(f"\n🤖 {content}")
        if not tool_calls:
            print("(no text output)" if not content else "")
            print("✅ Agent finished")
            return
        prefix = "\n" if content else ""
        for tool_call in tool_calls:
            function = tool_call["function"]["name"]
            arguments = json.loads(tool_call["function"]["arguments"])
            tool_call_id = tool_call["id"]
            print(f"{prefix}🔧 Tool: {function}({json.dumps(arguments, ensure_ascii=False)})")
            result = call_tool(function, arguments)
            print(f"   → {result[:500]}{'...' if len(result)>500 else ''}")
            messages.append({"role": "assistant", "content": content or None, "tool_calls": [tool_call]})
            messages.append({"role": "tool", "tool_call_id": tool_call_id, "content": result})
    print(f"\n⚠️  Max turns ({MAX_TURNS}) reached. Stopping.")


if __name__ == "__main__":
    prompt = " ".join(sys.argv[1:]) if len(sys.argv) > 1 else ""
    if not prompt.strip():
        print("No task provided. Exiting.")
        sys.exit(1)
    agent_loop(prompt)
