"""Orchestrator that coordinates subagents."""
import json
from typing import Optional
from concurrent.futures import ThreadPoolExecutor, as_completed

from chip.llm import LLMClient
from chip.tools import ToolRegistry
from chip.context.tracker import ContextTracker
from chip.ui.terminal import TerminalUI


ORCHESTRATOR_PROMPT = """You are an orchestrator. Your job is to:
1. Analyze the user's request
2. Break it into subtasks
3. Use subagents to complete each subtask
4. Combine results into a clear answer

You have access to subagents:
- search_agent(query) - searches the web
- fetch_agent(url) - reads web pages
- analyze_agent(data) - extracts key information

When you receive a request:
1. Decide which subagents to use
2. Call them in parallel when possible
3. Combine their results
4. Give a final human-readable answer

Be concise. Focus on getting the answer, not explaining the process."""


class Subagent:
    """A specialized worker that does one task."""
    
    def __init__(self, name: str, tools: ToolRegistry, llm: LLMClient):
        self.name = name
        self.tools = tools
        self.llm = llm
        self.tracker = ContextTracker(max_tokens=8000)
    
    def run(self, task: str) -> str:
        """Execute a task and return result."""
        messages = [
            {"role": "system", "content": f"You are {self.name}. Execute the task and return only the result."},
            {"role": "user", "content": task}
        ]
        
        for _ in range(5):
            try:
                response = self.llm.chat(messages, self.tools.to_openai_tools())
            except Exception as e:
                return f"Error: {e}"
            
            if response.content and not response.tool_calls:
                return response.content
            
            for tool_call in (response.tool_calls or []):
                func_name = tool_call["function"]["name"]
                try:
                    arguments = json.loads(tool_call["function"]["arguments"])
                except json.JSONDecodeError:
                    arguments = {}
                
                result = self.tools.call(func_name, arguments)
                
                messages.append({
                    "role": "assistant",
                    "content": response.content or None,
                    "tool_calls": [tool_call]
                })
                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result.output if result.success else f"Error: {result.error}"
                })
        
        return "Task completed"


class Orchestrator:
    """Main coordinator that manages subagents."""
    
    def __init__(self, llm: LLMClient, tools: ToolRegistry):
        self.llm = llm
        self.tools = tools
        self.ui = TerminalUI()
        self.tracker = ContextTracker(max_tokens=32000)
        
        # Create specialized subagents
        self.search_agent = Subagent("Search Agent", tools, llm)
        self.fetch_agent = Subagent("Fetch Agent", tools, llm)
        self.analyze_agent = Subagent("Analyze Agent", tools, llm)
    
    def process(self, user_message: str) -> str:
        """Process user request using subagents."""
        
        # Step 1: Plan - what subagents do we need?
        plan = self._create_plan(user_message)
        
        # Step 2: Execute subagents in parallel
        results = self._execute_plan(plan)
        
        # Step 3: Synthesize final answer
        answer = self._synthesize_answer(user_message, results)
        
        return answer
    
    def _create_plan(self, user_message: str) -> list[dict]:
        """Create execution plan."""
        query = user_message.lower()
        
        plan = []
        
        # Always search first for questions
        if any(w in query for w in ['что', 'как', 'где', 'когда', 'какой', 'какая', 'какое', 'почему', 'погод', 'новост', 'найди']):
            plan.append({
                "agent": "search",
                "task": user_message,
                "priority": 1
            })
        
        # If URL mentioned, fetch it
        if 'http' in query or 'сайт' in query or 'страниц' in query:
            urls = [word for word in query.split() if word.startswith('http')]
            if urls:
                plan.append({
                    "agent": "fetch",
                    "task": urls[0],
                    "priority": 2
                })
        
        # For code tasks
        if any(w in query for w in ['код', 'скрипт', 'программ', 'функци', 'класс']):
            plan.append({
                "agent": "analyze",
                "task": user_message,
                "priority": 3
            })
        
        # Default: just search
        if not plan:
            plan.append({
                "agent": "search",
                "task": user_message,
                "priority": 1
            })
        
        return plan
    
    def _execute_plan(self, plan: list[dict]) -> dict[str, str]:
        """Execute plan using subagents."""
        results = {}
        
        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = {}
            
            for step in plan:
                agent_name = step["agent"]
                task = step["task"]
                
                if agent_name == "search":
                    futures[executor.submit(self.search_agent.run, task)] = "search"
                elif agent_name == "fetch":
                    futures[executor.submit(self.fetch_agent.run, task)] = "fetch"
                elif agent_name == "analyze":
                    futures[executor.submit(self.analyze_agent.run, task)] = "analyze"
            
            for future in as_completed(futures):
                name = futures[future]
                try:
                    results[name] = future.result()
                except Exception as e:
                    results[name] = f"Error: {e}"
        
        return results
    
    def _synthesize_answer(self, user_message: str, results: dict[str, str]) -> str:
        """Synthesize final answer from subagent results."""
        # Combine all results
        combined = ""
        for name, result in results.items():
            combined += f"[{name.upper()}]\n{result}\n\n"
        
        # Ask LLM to synthesize
        messages = [
            {"role": "system", "content": "Synthesize the results into a clear, human-readable answer. Be concise."},
            {"role": "user", "content": f"User asked: {user_message}\n\nResults:\n{combined}"}
        ]
        
        try:
            response = self.llm.chat(messages)
            return response.content
        except Exception:
            # Fallback: return raw results
            return combined
