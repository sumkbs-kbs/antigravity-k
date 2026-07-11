import asyncio
import os
import sys

sys.path.append(os.path.abspath("src"))

from antigravity_k.tools.web_search import WebSearchTool


async def main():
    tool = WebSearchTool()
    print("Executing async search...")
    # This mimics what ToolExecutor.execute_async does
    result = await asyncio.to_thread(tool.execute, query="2026년 5월 5일 거제시 고현동 날씨")
    print("=" * 50)
    print(result)
    print("=" * 50)


if __name__ == "__main__":
    asyncio.run(main())
