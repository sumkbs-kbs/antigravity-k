import asyncio
from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.agents.trainer_agent import TrainerAgent


async def main():
    registry = ModelRegistry()
    manager = ModelManager(registry)
    agent = TrainerAgent(manager)
    print("Testing trainer...")
    try:
        res = agent.analyze_and_propose(
            [{"role": "user", "content": "hello"}],
            [{"role": "assistant", "content": "error here"}],
        )
        print("Success!", res)
    except Exception as e:
        print("Failed:", e)


asyncio.run(main())
