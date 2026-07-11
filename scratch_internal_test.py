import asyncio
import logging

from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.orchestrator import OrchestratorAgent

logging.basicConfig(level=logging.INFO)


async def run_test():
    print("Starting Internal Orchestrator Test...")
    model_manager = ModelManager()
    orchestrator = OrchestratorAgent(model_manager=model_manager)
    messages = [{"role": "user", "content": "파이썬의 주요 특징에 대해 간단히 분석해줄래?"}]
    target_model = "default"

    # We will consume the generator directly
    for chunk in orchestrator.run_stream(messages, target_model=target_model):
        print(chunk, end="", flush=True)
    print("\n--- Internal Test Complete ---")


asyncio.run(run_test())
