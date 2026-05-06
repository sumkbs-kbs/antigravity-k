import asyncio
import logging

logging.basicConfig(level=logging.INFO)

from antigravity_k.api.dependencies import get_model_manager
from antigravity_k.engine.orchestrator import OrchestratorAgent


async def run_test():
    print("Starting Internal Orchestrator Test using dependencies...")
    model_manager = get_model_manager()
    orchestrator = OrchestratorAgent(model_manager=model_manager)
    messages = [{"role": "user", "content": "최근 AI 트렌드에 대해 의견을 줘"}]
    target_model = "default"

    for chunk in orchestrator.run_stream(messages, target_model=target_model):
        print(chunk, end="", flush=True)
    print("\n--- Internal Test Complete ---")


asyncio.run(run_test())
