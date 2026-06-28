#!/usr/bin/env python3
"""Mock Ollama that searches AND reads pages."""
import json
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler

sys.path.insert(0, '/mnt/c/Users/user/chip')
from chip.tools import ToolRegistry

tools = ToolRegistry()

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
        
        # Get user message
        user_msg = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_msg = msg.get('content', '').lower()
                break
        
        # Check what tool calls we already have
        tool_calls_done = []
        for msg in messages:
            if msg.get('role') == 'assistant' and msg.get('tool_calls'):
                for tc in msg['tool_calls']:
                    tool_calls_done.append(tc['function']['name'])
        
        # Check if we have tool results
        tool_results = {}
        for msg in messages:
            if msg.get('role') == 'tool':
                tool_results[msg.get('tool_call_id', '')] = msg.get('content', '')
        
        # STEP 1: If no tools called yet, search first
        if not tool_calls_done:
            query = user_msg
            for w in ['найди', 'search', 'поиск', 'загугли', 'что сегодня', 'что нового', 'что интересного', 'какая', 'какой', 'какое']:
                query = query.replace(w, '').strip()
            if not query:
                query = user_msg
            
            result = tools.call('web_search', {'query': query, 'num_results': 3})
            
            # Extract first URL
            first_url = ""
            for line in result.output.split('\n'):
                if 'URL:' in line:
                    first_url = line.split('URL:')[1].strip()
                    break
            
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
                                "arguments": json.dumps({"query": query, "num_results": 3})
                            }
                        }]
                    }
                }]
            })
            return
        
        # STEP 2: If we searched but didn't fetch, fetch the first result
        if 'web_search' in tool_calls_done and 'web_fetch' not in tool_calls_done:
            # Get search results
            search_result = ""
            for msg in messages:
                if msg.get('role') == 'tool':
                    search_result = msg.get('content', '')
                    break
            
            # Extract first URL
            first_url = ""
            for line in search_result.split('\n'):
                if 'URL:' in line:
                    first_url = line.split('URL:')[1].strip()
                    break
            
            if first_url:
                result = tools.call('web_fetch', {'url': first_url, 'format': 'text'})
                
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
        
        # STEP 3: Build human-readable answer
        final_result = ""
        for msg in reversed(messages):
            if msg.get('role') == 'tool':
                final_result = msg.get('content', '')
                break
        
        # Extract key info and format nicely
        answer = self._build_human_answer(user_msg, final_result)
        
        self._send({
            "choices": [{"message": {"role": "assistant", "content": answer}}]
        })
    
    def _build_human_answer(self, query, raw_result):
        """Build a human-readable answer from raw results."""
        lines = raw_result.split('\n')
        
        # For weather queries
        if any(w in query for w in ['погод', 'weather', 'температур']):
            # Extract temperature and conditions
            temp_info = ""
            for line in lines:
                if '°' in line or 'температур' in line.lower() or '天气' in line:
                    temp_info += line.strip() + "\n"
            
            if temp_info:
                return f"**Погода:**\n\n{temp_info}\n\n[Источник: {lines[0] if lines else 'интернет'}]"
        
        # For other queries - extract first meaningful content
        content_lines = []
        skip_patterns = ['DOCTYPE', '<html', '<head', '<script', '<style', 'charset', 'viewport']
        
        for line in lines:
            line = line.strip()
            if not line or len(line) < 10:
                continue
            if any(p in line.lower() for p in skip_patterns):
                continue
            if line.startswith('{') or line.startswith('<'):
                continue
            content_lines.append(line)
            if len(content_lines) >= 10:
                break
        
        if content_lines:
            return "\n".join(content_lines[:10])
        
        return f"Информация найдена. Подробности:\n\n{raw_result[:1000]}"
    
    def _send(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(('127.0.0.1', 11434), MockHandler)
    print("Mock Ollama: search + fetch + answer")
    server.serve_forever()
