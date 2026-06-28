#!/usr/bin/env python3
"""
Mock Ollama with Orchestrator + Subagents pattern.

Architecture:
  User → Orchestrator → [Search Agent, Fetch Agent, Analyze Agent] → Answer
"""
import json
import sys
import re
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, '/mnt/c/Users/user/chip')
from chip.tools import ToolRegistry

tools = ToolRegistry()

# Track conversation state
conversation_state = {}


class MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/tags":
            self._send({"models": [{"name": "mock:latest", "model": "mock:latest"}]})
        else:
            self._send({"error": "not found"})

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        
        if self.path != "/v1/chat/completions":
            self._send({"error": "not found"})
            return
        
        messages = body.get('messages', [])
        
        # Get conversation ID (first user message hash)
        conv_id = "default"
        for msg in messages:
            if msg.get('role') == 'user':
                conv_id = str(hash(msg.get('content', '')))[:8]
                break
        
        state = conversation_state.get(conv_id, {"step": 0, "search_result": "", "fetch_result": ""})
        
        # Get user message
        user_msg = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_msg = msg.get('content', '')
                break
        
        # Check tool results
        tool_results = []
        for msg in messages:
            if msg.get('role') == 'tool':
                tool_results.append(msg.get('content', ''))
        
        # === ORCHESTRATOR LOGIC ===
        
        # Step 1: Search (if no search done yet)
        if state["step"] == 0:
            query = user_msg.lower()
            search_query = user_msg
            for w in ['найди', 'search', 'поиск', 'загугли', 'что сегодня', 'что нового', 'что интересного', 'какая', 'какой', 'какое']:
                search_query = search_query.replace(w, '').strip()
            if not search_query:
                search_query = user_msg
            
            # SEARCH AGENT
            search_result = tools.call('web_search', {'query': search_query, 'num_results': 3})
            state["search_result"] = search_result.output
            state["step"] = 1
            conversation_state[conv_id] = state
            
            # Extract first URL for fetching
            first_url = ""
            for line in search_result.output.split('\n'):
                if 'URL:' in line:
                    first_url = line.split('URL:')[1].strip()
                    break
            
            if first_url:
                self._send({
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": "call_search",
                                "type": "function",
                                "function": {
                                    "name": "web_search",
                                    "arguments": json.dumps({"query": search_query, "num_results": 3})
                                }
                            }]
                        }
                    }]
                })
                return
        
        # Step 2: Fetch (if search done but not fetched)
        if state["step"] == 1:
            first_url = ""
            for line in state["search_result"].split('\n'):
                if 'URL:' in line:
                    first_url = line.split('URL:')[1].strip()
                    break
            
            if first_url:
                # FETCH AGENT
                fetch_result = tools.call('web_fetch', {'url': first_url, 'format': 'text'})
                state["fetch_result"] = fetch_result.output
                state["step"] = 2
                conversation_state[conv_id] = state
                
                self._send({
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [{
                                "id": "call_fetch",
                                "type": "function",
                                "function": {
                                    "name": "web_fetch",
                                    "arguments": json.dumps({"url": first_url, "format": "text"})
                                }
                            }]
                        }
                    }]
                })
                return
        
        # Step 3: Analyze and answer
        if state["step"] == 2:
            # ANALYZE AGENT - extract key info
            answer = self._analyze_and_answer(user_msg, state["search_result"], state["fetch_result"])
            
            # Reset state
            conversation_state[conv_id] = {"step": 0, "search_result": "", "fetch_result": ""}
            
            self._send({
                "choices": [{"message": {"role": "assistant", "content": answer}}]
            })
            return
        
        # Default
        self._send({
            "choices": [{"message": {"role": "assistant", "content": "I can help with that! Ask me anything."}}]
        })
    
    def _analyze_and_answer(self, query, search_result, fetch_result):
        """ANALYZE AGENT: Extract and format answer."""
        lines = fetch_result.split('\n')
        
        # For weather
        if any(w in query.lower() for w in ['погод', 'weather', 'температур']):
            weather_info = []
            for line in lines:
                line = line.strip()
                if '°' in line and len(line) > 20:
                    weather_info.append(line)
                elif 'погода' in line.lower() and len(line) > 30:
                    weather_info.append(line)
            
            if weather_info:
                answer = "**Погода:**\n\n"
                for info in weather_info[:5]:
                    answer += f"• {info}\n"
                return answer
        
        # For news/articles
        if any(w in query.lower() for w in ['новост', 'стать', 'что нового', 'что интересное']):
            articles = []
            for line in lines:
                line = line.strip()
                if len(line) > 50 and not line.startswith('{') and not line.startswith('<'):
                    articles.append(line)
            
            if articles:
                answer = "**Интересное:**\n\n"
                for i, article in enumerate(articles[:5], 1):
                    answer += f"{i}. {article[:150]}\n"
                return answer
        
        # Generic answer
        content = []
        for line in lines:
            line = line.strip()
            if len(line) > 20 and not line.startswith('{') and not line.startswith('<'):
                content.append(line)
            if len(content) >= 10:
                break
        
        if content:
            return "\n".join(content)
        
        return f"Информация найдена. Вот что я нашёл:\n\n{fetch_result[:1000]}"
    
    def _send(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(('127.0.0.1', 11434), MockHandler)
    print("Orchestrator + Subagents Mock Server")
    print("Flow: User → Search → Fetch → Analyze → Answer")
    server.serve_forever()
