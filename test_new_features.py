import os
import sys

# 프로젝트 루트 경로 추가
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from antigravity_k.tools.artifact_tools import WriteArtifactTool
from antigravity_k.tools.cowork_delegate import CoworkDelegateTool
from antigravity_k.engine.task_runner import get_task_runner
import time

def test_write_artifact():
    print("=== Testing WriteArtifactTool ===")
    tool = WriteArtifactTool(project_root=os.getcwd())
    result = tool.execute(
        artifact_name="test_preview",
        content="<html><body><h1>Test Preview!</h1></body></html>",
        artifact_type="html"
    )
    print("Result:", result)
    assert "[ARTIFACT GENERATED: test_preview.html (Type: html)]" in result
    assert os.path.exists("artifacts/test_preview.html")
    print("✅ WriteArtifactTool passed\n")

def test_cowork_delegate():
    print("=== Testing CoworkDelegateTool ===")
    class MockManager:
        pass
    manager = MockManager()
    
    # It requires the database to be initialized by BackgroundTaskRunner
    tool = CoworkDelegateTool(project_root=os.getcwd(), model_manager=manager)
    result = tool.execute(
        prompt="Please write a quick summary of what you are.",
        use_worktree=True
    )
    print("Result:", result)
    assert "[COWORK DELEGATED]" in result
    
    # Check if task is running
    runner = get_task_runner()
    tasks = runner.list_tasks(limit=1)
    if tasks:
        print("Task found:", tasks[0]['task_id'], "| Status:", tasks[0]['status'])
    else:
        print("No tasks found in runner.")
    print("✅ CoworkDelegateTool passed\n")

if __name__ == "__main__":
    try:
        test_write_artifact()
        test_cowork_delegate()
        print("All tests completed successfully!")
    except Exception as e:
        print(f"Error during testing: {e}")
