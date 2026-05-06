import os
import sys

sys.path.append(os.path.abspath("src"))

from antigravity_k.tools.web_search import WebSearchTool

tool = WebSearchTool()
print("Executing search...")
result = tool.execute(query="2026년 5월 5일 거제시 고현동 날씨")
print("=" * 50)
print(result)
print("=" * 50)
