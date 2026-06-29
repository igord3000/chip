"""API key validation."""
import requests
from typing import Optional


def validate_api_key(provider: str, api_key: str, base_url: str) -> tuple[bool, str]:
    """Validate API key by making a test request.
    
    Returns:
        (is_valid, message)
    """
    if not api_key:
        return False, "API ключ не введён"
    
    # For Ollama, no API key needed
    if provider == "ollama":
        try:
            response = requests.get(f"{base_url}/../api/tags", timeout=5)
            if response.status_code == 200:
                return True, "Ollama доступен"
            return False, f"Ollama недоступен: {response.status_code}"
        except Exception as e:
            return False, f"Cannot connect to Ollama: {e}"
    
    # For cloud providers, test with models endpoint
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Try to list models (most providers support this)
        response = requests.get(
            f"{base_url}/models",
            headers=headers,
            timeout=10
        )
        
        if response.status_code == 200:
            return True, "API ключ валиден"
        elif response.status_code == 401:
            return False, "Неверный API ключ"
        elif response.status_code == 403:
            return False, "Нет доступа к API"
        else:
            return False, f"Ошибка: {response.status_code}"
            
    except requests.exceptions.Timeout:
        return False, "Таймаут подключения"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to API"
    except Exception as e:
        return False, f"Ошибка: {e}"


def test_chat_completion(provider: str, api_key: str, base_url: str, model: str) -> tuple[bool, str]:
    """Test chat completion to verify API works.
    
    Returns:
        (is_valid, message)
    """
    if not api_key and provider != "ollama":
        return False, "API ключ не введён"
    
    try:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": "Say hello"}],
            "max_tokens": 10
        }
        
        response = requests.post(
            f"{base_url}/chat/completions",
            json=payload,
            headers=headers,
            timeout=30
        )
        
        if response.status_code == 200:
            data = response.json()
            if "choices" in data and len(data["choices"]) > 0:
                return True, "Модель работает корректно"
            return False, "Пустой ответ от модели"
        elif response.status_code == 401:
            return False, "Неверный API ключ"
        elif response.status_code == 404:
            return False, f"Модель '{model}' не найдена"
        else:
            return False, f"Ошибка: {response.status_code} - {response.text[:100]}"
            
    except requests.exceptions.Timeout:
        return False, "Таймаут (модель загружается?)"
    except requests.exceptions.ConnectionError:
        return False, "Cannot connect to API"
    except Exception as e:
        return False, f"Ошибка: {e}"
