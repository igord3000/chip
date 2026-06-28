#!/usr/bin/env python3
"""Mock Ollama that calls REAL tools."""
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
        
        # Check if we have tool results
        has_tool_results = any(m.get('role') == 'tool' for m in messages)
        
        if has_tool_results:
            # Build response from last tool result
            for msg in reversed(messages):
                if msg.get('role') == 'tool':
                    result = msg.get('content', '')
                    response_text = f"Based on the search results:\n\n{result[:1500]}\n\nWould you like me to get more details?"
                    self._send({
                        "choices": [{"message": {"role": "assistant", "content": response_text}}]
                    })
                    return
        
        # Call REAL tools
        if any(w in user_msg for w in ['найди', 'search', 'поиск', 'загугли', 'погод', 'новост', 'стать', 'что', 'как', 'где', 'когда', 'какой', 'какая']):
            query = user_msg
            for w in ['найди', 'search', 'поиск', 'загугли', 'что сегодня', 'что нового', 'что интересного']:
                query = query.replace(w, '').strip()
            if not query:
                query = user_msg
            
            # Actually call web_search
            result = tools.call('web_search', {'query': query, 'num_results': 5})
            
            self._send({
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "web_search",
                                "arguments": json.dumps({"query": query, "num_results": 5})
                            }
                        }]
                    }
                }]
            })
            return
        
        if any(w in user_msg for w in ['прочитай', 'fetch', 'открой', 'покажи страницу']):
            url = "https://" + user_msg
            for w in ['прочитай', 'fetch', 'открой', 'покажи', 'страницу']:
                url = url.replace(w, '').strip()
            if 'http' not in url:
                url = "https://" + url
            
            self._send({
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": None,
                        "tool_calls": [{
                            "id": "call_1",
                            "type": "function",
                            "function": {
                                "name": "web_fetch",
                                "arguments": json.dumps({"url": url, "format": "text"})
                            }
                        }]
                    }
                }]
            })
            return
        
        # Default response
        self._send({
            "choices": [{"message": {"role": "assistant", "content": f"I can help with that! Ask me to search, fetch a URL, or work with code."}}]
        })
    
    def _send(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(('127.0.0.1', 11434), MockHandler)
    print("Mock Ollama with REAL tools running on http://127.0.0.1:11434")
    server.serve_forever()
