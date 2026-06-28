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
            
            # Simple responses based on content
            content = last_msg.get('content', '')
            
            if 'hello' in content.lower() or 'привет' in content.lower():
                response_text = "Hello! How can I help you?"
            elif 'write' in content.lower() or 'создай' in content.lower():
                # Return tool call to write a file
                response = {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": "I'll create a hello.py file for you.",
                            "tool_calls": [{
                                "id": "call_1",
                                "type": "function",
                                "function": {
                                    "name": "write_file",
                                    "arguments": json.dumps({"path": "hello.py", "content": 'print("Hello, World!")'})
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
                response_text = f"I understand your request: '{content[:50]}...' How can I help?"
            
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
