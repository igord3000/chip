#!/usr/bin/env python3
"""Mock Ollama server for testing Chip agent."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

class MockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/tags":
            response = {
                "models": [
                    {
                        "name": "mock:latest",
                        "model": "mock:latest",
                        "modified_at": "2025-01-01T00:00:00Z",
                        "size": 1000000,
                        "digest": "abc123"
                    }
                ]
            }
        else:
            response = {"error": "not found"}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = json.loads(self.rfile.read(content_length))
        
        if self.path == "/v1/chat/completions":
            messages = body.get('messages', [])
            last_msg = messages[-1] if messages else {}
            content = last_msg.get('content', '').lower()
            
            if 'hello' in content or 'привет' in content:
                response_text = "Hello! I can help you with programming and internet research."
            elif 'search' in content or 'найди' in content:
                response = {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": "I'll search the web for that information.",
                            "tool_calls": [{
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "web_search",
                                    "arguments": json.dumps({"query": "Python programming tutorial", "num_results": 3})
                                }
                            }]
                        }
                    }]
                }
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
                return
            elif 'fetch' in content or 'скачай' in content or 'прочитай' in content:
                response = {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": "I'll fetch that URL for you.",
                            "tool_calls": [{
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "web_fetch",
                                    "arguments": json.dumps({"url": "https://httpbin.org/json", "format": "text"})
                                }
                            }]
                        }
                    }]
                }
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(json.dumps(response).encode())
                return
            else:
                response_text = f"I understand: '{content[:50]}...' I can search the web, fetch URLs, or help with code."
            
            response = {
                "choices": [{
                    "message": {
                        "role": "assistant",
                        "content": response_text
                    }
                }]
            }
        else:
            response = {"error": "not found"}
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(response).encode())
    
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(('127.0.0.1', 11434), MockHandler)
    print("Mock Ollama server running on http://127.0.0.1:11434")
    print("Press Ctrl+C to stop")
    server.serve_forever()
