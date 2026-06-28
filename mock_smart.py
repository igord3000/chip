#!/usr/bin/env python3
"""Smart mock that handles different query types."""
import json
import random
from http.server import HTTPServer, BaseHTTPRequestHandler

# Responses for different query types
RESPONSES = {
    "greeting": [
        "Привет! У меня всё отлично, спасибо! Чем могу помочь?",
        "Привет! Хорошо, работаю! Задавай вопрос!",
        "Привет! Всё супер! Как дела у тебя?"
    ],
    "joke": [
        "— Почему программист путает Хеллоуин и Рождество?\n— Потому что Oct 31 = Dec 25!\n(31 в восьмеричной = 25 в десятичной)",
        "Программист: 'У меня нет багов, только фичи!'",
        "Два байта встретились. Один спрашивает: 'Ты в порядке?' Второй: 'Нет, у меня переполнение...'"
    ],
    "weather_miass": """**Погода в Миассе сейчас:**
• Облачно с прояснениями
• Температура: +18°C (ощущается как +16°C)
• Ветер: 2.9 м/с, северный
• Давление: 721 мм рт. ст.
• Влажность: 56%
• Восход: 21:42, Закат: 04:23""",
    
    "python_news": """**Новости Python:**
• Python 3.13 — новый JIT компилятор
• Улучшена производительность на 5-10%
• PEP 703 — Optional GIL (экспериментальный)
• Новый модуль для работы с типами
• Улучшена документация""",
    
    "default": "Я могу помочь с поиском информации, погодой, новостями и кодом. Задайте конкретный вопрос!"
}


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
        has_results = any(m.get('role') == 'tool' for m in messages)
        
        if has_results:
            # Get last tool result
            for msg in reversed(messages):
                if msg.get('role') == 'tool':
                    result = msg.get('content', '')
                    # Try to extract answer from result
                    answer = self._extract_answer(user_msg, result)
                    self._send({"choices": [{"message": {"role": "assistant", "content": answer}}]})
                    return
        
        # Classify query and respond
        answer = self._classify_and_respond(user_msg)
        self._send({"choices": [{"message": {"role": "assistant", "content": answer}}]})
    
    def _classify_and_respond(self, query):
        """Classify query type and return appropriate response."""
        query = query.lower().strip()
        
        # Greetings
        if any(w in query for w in ['привет', 'здравствуй', 'добрый', 'hello', 'hi', 'йо']):
            return random.choice(RESPONSES["greeting"])
        
        # Jokes
        if any(w in query for w in ['анекдот', 'шутк', 'joke', 'смешн', 'рассмеши']):
            return random.choice(RESPONSES["joke"])
        
        # Weather
        if any(w in query for w in ['погод', 'weather', 'температур', 'градус']):
            if 'миасс' in query or 'миас' in query:
                return RESPONSES["weather_miass"]
            return "Уточните город для прогноза погоды."
        
        # Python
        if any(w in query for w in ['python', 'пайтон', 'питон']):
            return RESPONSES["python_news"]
        
        # Search needed
        if any(w in query for w in ['найди', 'search', 'что', 'как', 'где', 'когда', 'почему']):
            return self._search_and_respond(query)
        
        return RESPONSES["default"]
    
    def _search_and_respond(self, query):
        """Search and return formatted response."""
        import sys
        sys.path.insert(0, '/mnt/c/Users/user/chip')
        from chip.tools import ToolRegistry
        
        tools = ToolRegistry()
        result = tools.call('web_search', {'query': query, 'num_results': 3})
        
        if result.success and "No results" not in result.output:
            # Extract first meaningful result
            lines = result.output.split('\n')
            for line in lines:
                if line.strip() and not line.startswith('Search results') and 'URL:' not in line and len(line.strip()) > 20:
                    return f"Вот что я нашёл:\n\n{line.strip()}"
        
        return "Не нашёл конкретной информации. Попробуйте перефразировать вопрос."
    
    def _extract_answer(self, query, raw_result):
        """Extract answer from tool result."""
        if any(w in query for w in ['погод', 'weather']):
            return RESPONSES["weather_miass"]
        
        lines = raw_result.split('\n')
        for line in lines:
            if line.strip() and len(line.strip()) > 20 and not line.startswith('Search'):
                return line.strip()
        
        return raw_result[:500]
    
    def _send(self, data):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    
    def log_message(self, format, *args):
        pass

if __name__ == "__main__":
    server = HTTPServer(('127.0.0.1', 11434), MockHandler)
    print("Smart Mock: greetings, jokes, weather, python, search")
    server.serve_forever()
