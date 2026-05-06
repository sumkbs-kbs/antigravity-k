import asyncio
import os
import sys

sys.path.append(os.path.abspath("src"))

from antigravity_k.tools.web_search import WebSearchTool


async def async_generator():
    tool = WebSearchTool()
    print("Executing search inside async generator (simulating orchestrator)...")
    try:
        # orchestrator.py does: tool_result = self._execute_tool(tool_name, tool_args)
        # which calls ToolExecutor.execute synchronously!
        result = tool.execute(query="2026년 5월 5일 거제시 고현동 날씨")
        print("Result starts with Error?", str(result).strip().startswith("Error"))
        print(str(result)[:500])
    except Exception as e:
        print(f"Exception escaped! {type(e)}: {e}")


if __name__ == "__main__":
    asyncio.run(async_generator())
