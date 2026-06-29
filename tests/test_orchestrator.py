"""Test orchestrator and subagents."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from chip.orchestrator import Orchestrator
from chip.config import load_config


def test_orchestrator():
    """Test orchestrator with various queries."""
    config = load_config()
    orch = Orchestrator(config)
    
    print("=" * 60)
    print("Orchestrator Test")
    print("=" * 60)
    
    # Test queries
    queries = [
        "Какая погода в Миассе сегодня?",
        "Какая погода в Миассе на неделю и на месяц?",
        "Что такое Python и как его установить?",
        "Привет, как дела?",
    ]
    
    for query in queries:
        print(f"\n{'─' * 60}")
        print(f"Query: {query}")
        print(f"{'─' * 60}")
        
        # Execute with orchestrator
        result = orch.execute(query, callback=lambda msg: print(f"  → {msg}"))
        
        print(f"Success: {result.success}")
        print(f"Tools used: {result.tools_called}")
        print(f"Duration: {result.duration_ms}ms")
        print(f"Answer: {result.answer[:300]}...")
    
    print(f"\n{'=' * 60}")
    print("Test completed!")


if __name__ == "__main__":
    test_orchestrator()
