"""Automated tests for Chip agent."""
import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))


class TestRunner:
    """Simple test runner."""
    
    def __init__(self):
        self.results = []
        self.passed = 0
        self.failed = 0
    
    def test(self, name: str, func):
        try:
            func()
            self.results.append({"name": name, "status": "PASS"})
            self.passed += 1
            print(f"  ✓ {name}")
        except Exception as e:
            self.results.append({"name": name, "status": "FAIL", "error": str(e)})
            self.failed += 1
            print(f"  ✗ {name}: {e}")
    
    def summary(self):
        total = self.passed + self.failed
        print(f"\n{'='*40}")
        print(f"Results: {self.passed}/{total} passed")
        if self.failed:
            print(f"Failed: {self.failed}")
        return self.failed == 0


def test_config():
    """Test config loading."""
    from chip.config import load_config
    config = load_config()
    assert config.llm.model, "Model not set"
    assert config.llm.base_url, "Base URL not set"
    assert config.llm.max_tokens > 0, "Max tokens must be positive"


def test_providers():
    """Test provider manager."""
    from chip.providers import ProviderManager
    manager = ProviderManager()
    providers = manager.list_providers()
    assert len(providers) > 0, "No providers found"
    assert "ollama" in [p[0] for p in providers], "Ollama provider missing"


def test_tools():
    """Test tool registry."""
    from chip.tools import ToolRegistry
    tools = ToolRegistry()
    expected = ["bash", "read_file", "write_file", "list_files", 
                "web_search", "web_fetch", "download", "subagent"]
    for tool in expected:
        assert tool in tools.tool_names, f"Tool {tool} missing"
    
    # Test bash tool
    result = tools.call("bash", {"command": "echo test"})
    assert result.success, f"Bash tool failed: {result.error}"
    assert "test" in result.output, "Bash output incorrect"


def test_cache():
    """Test caching."""
    from chip.cache import ResponseCache, SemanticCache
    import tempfile
    
    # Test ResponseCache
    cache = ResponseCache(Path(tempfile.mkdtemp()))
    messages = [{"role": "user", "content": "test"}]
    cache.set(messages, "test response")
    result = cache.get(messages)
    assert result == "test response", "Cache get failed"
    
    # Test SemanticCache
    sem_cache = SemanticCache()
    sem_cache.set("what is python", "Python is a language")
    result = sem_cache.get("what is python", threshold=0.3)
    assert result is not None, "Semantic cache failed"


def test_router():
    """Test query router."""
    from chip.router import QueryRouter, QueryType
    
    router = QueryRouter()
    
    # Test different query types
    assert router.route("привет") == QueryType.CONVERSATION
    assert router.route("что такое Python") == QueryType.KNOWLEDGE
    assert router.route("какая погода") == QueryType.CURRENT_DATA
    assert router.route("напиши код") == QueryType.CODE
    assert router.route("найди информацию") == QueryType.SEARCH


def test_api_validator():
    """Test API validation (mock)."""
    from chip.api_validator import validate_api_key
    
    # Test empty key
    is_valid, msg = validate_api_key("ollama", "", "http://localhost:11434/v1")
    assert not is_valid, "Empty key should be invalid"


def test_memory():
    """Test memory system."""
    from chip.memory import Memory
    import tempfile
    
    memory = Memory(Path(tempfile.mkdtemp()))
    memory.remember("Python is great", "tech")
    
    results = memory.recall("Python")
    assert len(results) > 0, "Memory recall failed"
    assert "Python" in results[0], "Memory content incorrect"


def test_context_tracker():
    """Test context tracker."""
    from chip.context.tracker import ContextTracker
    
    tracker = ContextTracker(max_tokens=1000)
    messages = [{"role": "user", "content": "test message"}]
    tokens = tracker.update(messages)
    
    assert tokens > 0, "Token count should be positive"
    assert tracker.usage_percent >= 0, "Usage percent should be non-negative"
    assert not tracker.is_critical, "Should not be critical at low usage"


def test_recovery():
    """Test error recovery."""
    from chip.recovery import ErrorRecovery
    
    recovery = ErrorRecovery()
    suggestions = recovery.suggest_recovery(ConnectionError("test"))
    assert len(suggestions) > 0, "Should have suggestions"


def test_llm_client():
    """Test LLM client initialization."""
    from chip.llm import LLMClient
    from chip.config import LLMConfig
    
    config = LLMConfig()
    client = LLMClient(config)
    assert client.config == config, "Config not set"


def test_subagent():
    """Test subagent manager."""
    from chip.subagent import SubagentManager
    from chip.config import load_config
    
    config = load_config()
    manager = SubagentManager(config)
    
    task_id = manager.spawn("test task")
    assert task_id, "Task ID should be generated"
    assert task_id in manager.tasks, "Task should be in manager"


def run_all_tests():
    """Run all tests."""
    print("=" * 40)
    print("Chip Agent - Automated Tests")
    print("=" * 40)
    
    runner = TestRunner()
    
    print("\nCore tests:")
    runner.test("Config loading", test_config)
    runner.test("Provider manager", test_providers)
    runner.test("Tool registry", test_tools)
    runner.test("Cache system", test_cache)
    runner.test("Query router", test_router)
    
    print("\nFeature tests:")
    runner.test("API validator", test_api_validator)
    runner.test("Memory system", test_memory)
    runner.test("Context tracker", test_context_tracker)
    runner.test("Error recovery", test_recovery)
    runner.test("LLM client", test_llm_client)
    runner.test("Subagent manager", test_subagent)
    
    return runner.summary()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
