#!/usr/bin/env python3
"""Smart mock Ollama server that simulates tool usage."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

class SmartMockHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/tags":
            response = {
                "models": [{"name": "mock:latest", "model": "mock:latest"}]
            }
        else:
            response = {"error": "not found"}
        self._send(response)

    def do_POST(self):
        body = json.loads(self.rfile.read(int(self.headers.get('Content-Length', 0))))
        
        if self.path == "/v1/chat/completions":
            messages = body.get('messages', [])
            tools = body.get('tools', [])
            
            # Determine what tool to call based on conversation
            tool_call = self._decide_tool(messages, tools)
            
            if tool_call:
                response = {
                    "choices": [{
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [tool_call]
                        }
                    }]
                }
            else:
                # Final response after tools have been used
                last_assistant = None
                for msg in reversed(messages):
                    if msg.get('role') == 'assistant' and msg.get('content'):
                        last_assistant = msg['content']
                        break
                    if msg.get('role') == 'tool':
                        # Build response from tool results
                        tool_content = msg.get('content', '')
                        response_text = self._build_response(messages)
                        response = {
                            "choices": [{
                                "message": {
                                    "role": "assistant",
                                    "content": response_text
                                }
                            }]
                        }
                        self._send(response)
                        return
                
                response_text = "I can help with that! Ask me to search, fetch a URL, or work with code."
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
        
        self._send(response)

    def _decide_tool(self, messages, tools):
        """Decide which tool to call based on the conversation."""
        if not tools:
            return None
            
        # Get the latest user message
        user_msg = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_msg = msg.get('content', '').lower()
                break
        
        # Check if we already have tool results in this conversation
        has_tool_results = any(m.get('role') == 'tool' for m in messages)
        if has_tool_results:
            return None
        
        # Decide tool based on user message
        if any(word in user_msg for word in ['найди', 'search', 'поиск', 'загугли', 'google']):
            query = user_msg
            for word in ['найди', 'search', 'поиск', 'загугли', 'google']:
                query = query.replace(word, '').strip()
            return {
                "id": "call_search_1",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": json.dumps({"query": query or "information", "num_results": 5})
                }
            }
        
        if any(word in user_msg for word in ['прочитай', 'fetch', 'открой', 'скачай страницу']):
            url = "https://habr.com/ru/rss/articles/"
            for word in ['прочитай', 'fetch', 'открой', 'скачай страницу']:
                user_msg = user_msg.replace(word, '').strip()
            if 'habr' in user_msg or 'хабр' in user_msg:
                url = "https://habr.com/ru/rss/articles/"
            elif 'http' in user_msg:
                url = user_msg
            return {
                "id": "call_fetch_1",
                "type": "function",
                "function": {
                    "name": "web_fetch",
                    "arguments": json.dumps({"url": url, "format": "text"})
                }
            }
        
        if any(word in user_msg for word in ['habr', 'хабр', 'habр']):
            # First search for habr, then fetch RSS
            return {
                "id": "call_search_habr",
                "type": "function",
                "function": {
                    "name": "web_search",
                    "arguments": json.dumps({"query": "habr.com сегодня интересное", "num_results": 5})
                }
            }
        
        if any(word in user_msg for word in ['скачай', 'download', 'файл']):
            url = "https://example.com/file.zip"
            return {
                "id": "call_download_1",
                "type": "function",
                "function": {
                    "name": "download",
                    "arguments": json.dumps({"url": url})
                }
            }
        
        return None

    def _build_response(self, messages):
        """Build a response from tool results."""
        tool_results = []
        for msg in messages:
            if msg.get('role') == 'tool':
                tool_results.append(msg.get('content', ''))
        
        if tool_results:
            result = tool_results[-1]
            if len(result) > 1000:
                result = result[:1000] + "..."
            return f"Based on the search results:\n\n{result}\n\nWould you like me to get more details?"
        
        return "I found some information. Would you like me to look for anything specific?"

    def _send(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(('127.0.0.1', 11434), SmartMockHandler)
    print("Smart Mock Ollama running on http://127.0.0.1:11434")
    print("Simulates tool calls for: search, fetch, download")
    print("Press Ctrl+C to stop")
    server.serve_forever()
