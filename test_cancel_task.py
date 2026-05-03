import os
import sys
import time

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "src")))

from antigravity_k.engine.task_runner import get_task_runner
from antigravity_k.engine.orchestrator import OrchestratorAgent
from antigravity_k.engine.model_manager import ModelManager

def test_cancel_task():
    class MockManager:
        pass
    manager = MockManager()
    print("=== Testing cancel_task ===")
    runner = get_task_runner()
    
    # Clean old tasks if needed, or just run a new one
    orchestrator = OrchestratorAgent(model_manager=manager)
    
    # We will submit a task that takes some time
    prompt = "Please count from 1 to 100 very slowly."
    task_id = runner.submit_task(prompt, context={"use_worktree": True}, orchestrator=orchestrator)
    
    print(f"Submitted task: {task_id}")
    time.sleep(1) # Let it start running
    
    status = runner.get_status(task_id)
    print(f"Status before cancel: {status['status']}")
    
    print(f"Cancelling task {task_id}...")
    success = runner.cancel_task(task_id)
    print(f"Cancel success: {success}")
    
    time.sleep(1) # Wait for thread to notice the event and abort
    
    status = runner.get_status(task_id)
    print(f"Status after cancel: {status['status']}")
    
    if status['status'] == 'cancelled':
        print("✅ Task was successfully cancelled.")
    else:
        print("❌ Task cancellation failed.")

if __name__ == "__main__":
    test_cancel_task()
