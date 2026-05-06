from antigravity_k.engine.model_registry import ModelRegistry
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.tools.tool_registry import ToolRegistry
from antigravity_k.engine.orchestrator import OrchestratorAgent
import asyncio


async def main():
    reg = ModelRegistry()
    mm = ModelManager(registry=reg)
    tr = ToolRegistry()
    orch = OrchestratorAgent(model_manager=mm, tool_registry=tr)

    messages = [
        {
            "role": "user",
            "content": "현재 작업 디렉토리에 'test_agk_folder'라는 폴더를 만들고, 그 안에 'test_agk_file.py'라는 파이썬 파일을 생성해 줘. 파일 내용으로는 'print(\"Hello Antigravity\")'가 들어가야 해.",
        }
    ]

    try:
        for chunk in orch.run_stream(
            messages, target_model="qwen3.6:latest", max_steps=15
        ):
            print(chunk, end="", flush=True)
    except Exception as e:
        print("\n\nEXCEPTION CAUGHT IN SCRIPT:\n")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    asyncio.run(main())
