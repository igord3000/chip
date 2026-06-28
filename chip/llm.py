"""LLM client with error handling and retries."""
import json
from typing import Any, Optional
from dataclasses import dataclass

import requests

from chip.config import LLMConfig


@dataclass
class LLMResponse:
    content: str
    tool_calls: list[dict[str, Any]]


class LLMClient:
    def __init__(self, config: LLMConfig):
        self.config = config
        self.headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {config.api_key}"
        }

    def chat(self, messages: list[dict], tools: Optional[list[dict]] = None) -> LLMResponse:
        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            response = requests.post(
                f"{self.config.base_url}/chat/completions",
                json=payload,
                headers=self.headers,
                timeout=self.config.timeout
            )
            response.raise_for_status()

            data = response.json()
            msg = data["choices"][0]["message"]

            content = (msg.get("content") or "").strip()
            tool_calls = msg.get("tool_calls") or []

            return LLMResponse(content=content, tool_calls=tool_calls)

        except requests.exceptions.Timeout:
            raise ConnectionError(f"LLM request timed out after {self.config.timeout}s")
        except requests.exceptions.ConnectionError:
            raise ConnectionError(f"Cannot connect to LLM at {self.config.base_url}")
        except requests.exceptions.HTTPError as e:
            raise ConnectionError(f"LLM HTTP error: {e.response.status_code} - {e.response.text[:200]}")
        except (KeyError, IndexError, json.JSONDecodeError) as e:
            raise ValueError(f"Invalid LLM response format: {e}")
