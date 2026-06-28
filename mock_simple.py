#!/usr/bin/env python3
"""Simple mock - returns answers directly without tool calls."""
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

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
        
        # Count user messages
        user_count = sum(1 for m in messages if m.get('role') == 'user')
        
        # Get user message
        user_msg = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_msg = msg.get('content', '').lower()
                break
        
        # Check if we have tool results
        has_results = any(m.get('role') == 'tool' for m in messages)
        
        if has_results:
            # Build answer from results
            for msg in reversed(messages):
                if msg.get('role') == 'tool':
                    result = msg.get('content', '')
                    # Format nicely
                    answer = self._format_answer(user_msg, result)
                    self._send({"choices": [{"message": {"role": "assistant", "content": answer}}]})
                    return
        
        # First call: search
        if user_count <= 1:
            query = user_msg
            for w in ['найди', 'search', 'поиск', 'что сегодня', 'что нового', 'какая', 'какой', 'какое']:
                query = query.replace(w, '').strip()
            if not query:
                query = user_msg
            
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
                                "arguments": json.dumps({"query": query, "num_results": 3})
                            }
                        }]
                    }
                }]
            })
            return
        
        # Default
        self._send({
            "choices": [{"message": {"role": "assistant", "content": "I can help! Ask me anything."}}]
        })
    
    def _format_answer(self, query, raw):
        """Format answer based on query type."""
        if any(w in query for w in ['погод', 'weather']):
            return """**Погода в Миассе:**
• Облачно с прояснениями
• Температура: +18°C (ощущается +16°C)
• Ветер: 2.9 м/с, северный
• Давление: 721 мм рт. ст.
• Влажность: 56%"""
        
        if any(w in query for w in ['python', 'пайтон']):
            return """**Новости Python:**
• Python 3.13 - новый JIT компилятор
• Улучшена производительность на 5-10%
• Новый модуль для работы с типами
• PEP 703 - Optional GIL"""
        
        if any(w in query for w in ['новост', 'что нового']):
            return f"Информация найдена. Вот что я нашёл:\n\n{raw[:500]}"
        
        return f"Результат:\n\n{raw[:500]}"
    
    def _send(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(('127.0.0.1', 11434), MockHandler)
    print("Simple Mock Server")
    server.serve_forever()
