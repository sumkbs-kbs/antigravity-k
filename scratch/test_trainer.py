import asyncio

from antigravity_k.agents.trainer_agent import TrainerAgent
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.tools.tool_registry import ToolRegistry


async def main():
    registry = ModelRegistry()
    manager = ModelManager(registry)
    agent = TrainerAgent(manager, ToolRegistry())
    print("Testing trainer...")
    try:
        res = agent.propose_training("hello")
        print("Success!", res)
    except Exception as e:
        print("Failed:", e)


asyncio.run(main())
