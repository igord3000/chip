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
        "Найди информацию про Ollama и покажи как установить",
        "Привет, как дела?",  # Simple query - no subagents
    ]
    
    for query in queries:
        print(f"\n{'─' * 60}")
        print(f"Query: {query}")
        print(f"{'─' * 60}")
        
        # Check if should use subagents
        use_sub = orch.should_use_subagents(query)
        print(f"Use subagents: {use_sub}")
        
        if use_sub:
            subtasks = orch.split_into_subtasks(query)
            print(f"Subtasks: {subtasks}")
        
        # Execute
        result = orch.execute(query)
        
        print(f"Success: {result.success}")
        print(f"Answer: {result.answer[:300]}...")
        
        if result.subtasks:
            print(f"Subtask results:")
            for r in (result.subtask_results or []):
                print(f"  {r[:100]}...")
    
    print(f"\n{'=' * 60}")
    print("Test completed!")


if __name__ == "__main__":
    test_orchestrator()
