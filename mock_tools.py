#!/usr/bin/env python3
"""Smart mock that calls real tools."""
import json
import sys
sys.path.insert(0, '/mnt/c/Users/user/chip')

from chip.tools import ToolRegistry

tools = ToolRegistry()

class SmartMockHandler:
    def handle(self, messages, tool_calls_from_llm=None):
        """Process messages and return response."""
        # Get last user message
        user_msg = ""
        for msg in reversed(messages):
            if msg.get('role') == 'user':
                user_msg = msg.get('content', '').lower()
                break
        
        # Check if we have tool results already
        has_tool_results = any(m.get('role') == 'tool' for m in messages)
        
        if has_tool_results:
            # Build response from tool results
            for msg in reversed(messages):
                if msg.get('role') == 'tool':
                    result = msg.get('content', '')
                    return {"content": f"Based on the search results:\n\n{result[:1000]}\n\nWould you like more details?", "tool_calls": None}
        
        # Decide which tool to call
        if any(w in user_msg for w in ['найди', 'search', 'поиск', 'загугли', 'погод', 'новост', 'стать', 'что', 'как', 'где', 'когда']):
            query = user_msg
            for w in ['найди', 'search', 'поиск', 'загугли', 'что сегодня', 'что нового']:
                query = query.replace(w, '').strip()
            if not query:
                query = user_msg
            
            # Call real web_search tool
            result = tools.call('web_search', {'query': query, 'num_results': 5})
            
            return {
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
        
        if any(w in user_msg for w in ['прочитай', 'fetch', 'открой', 'отобрази', 'покажи']):
            url = user_msg
            for w in ['прочитай', 'fetch', 'открой', 'отобрази', 'покажи', 'страницу']:
                url = url.replace(w, '').strip()
            if 'http' not in url:
                url = "https://" + url
            
            return {
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
        
        # Default: simple response
        return {"content": f"I understand: '{user_msg[:50]}...' How can I help?", "tool_calls": None}

handler = SmartMockHandler()
