import os
import sys

sys.path.append(os.path.abspath("src"))

from antigravity_k.engine.tool_executor import ToolExecutor
from antigravity_k.tools.tool_registry import ToolRegistry
from antigravity_k.tools.permission_gate import PermissionGate
from antigravity_k.tools.web_search import WebSearchTool


def main():
    registry = ToolRegistry(project_root=".")
    registry.install(WebSearchTool())

    executor = ToolExecutor(
        tool_registry=registry, permission_gate=PermissionGate(project_root=".")
    )

    # Simulate missing query
    result = executor.execute("web_search", {})
    print("Missing query result:", repr(result))

    # Simulate correct query
    result2 = executor.execute(
        "web_search", {"query": "2026년 5월 5일 거제시 고현동 날씨"}
    )
    print("Valid query result:", type(result2))


if __name__ == "__main__":
    main()
