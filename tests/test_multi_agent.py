import json
import logging

# 테스트 로깅 설정
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

from src.antigravity_k.agents.commands import CommandHandler
from src.antigravity_k.agents.message_bus import MessageBus
from src.antigravity_k.agents.team_manager import TeamManager
from src.antigravity_k.engine.model_manager import ModelManager
from src.antigravity_k.engine.model_registry import ModelRegistry
from src.antigravity_k.knowledge.memory_service import MemoryService


def run_test():
    print("=== Ssakfile Pro Advanced Multi-Agent System Test ===\n")

    # 0. 메모리 시스템 초기화 확인
    memory = MemoryService()
    memory.save_snapshot("SYS", {"status": "test_start"})
    print("[Memory Service] Initialized and snapshot saved.")

    # 1. TeamManager 및 ModelManager 초기화
    registry = ModelRegistry()
    model_manager = ModelManager(registry)
    manager = TeamManager(model_manager=model_manager)

    # 2. CommandHandler 연결
    cmd_handler = CommandHandler(manager)

    # 3. MessageBus 채널 설정 및 콜백 테스트
    bus = MessageBus()
    bus.create_channel("general")

    def on_message(msg):
        print(f"[Event Callback Triggered] {msg}")

    bus.subscribe_callback("general", on_message)

    print("\n[User Command] /tasks (Before adding tasks)")
    print(cmd_handler.execute("/tasks"))

    print("\n[User Command] /review 'Implement dynamic model loading with MLX backend'")
    print(cmd_handler.execute("/review 'Implement dynamic model loading with MLX backend'"))

    print("\n[User Command] /tasks (After review command)")
    print(cmd_handler.execute("/tasks"))

    print("\n[User Command] /status")
    print(cmd_handler.execute("/status"))

    print("\n=== Running Team Cycle ===")
    # 자율 에이전트 협업 사이클 실행 (Mock)
    manager.run_team_cycle()

    print("\n[User Command] /tasks (After team cycle)")
    print(cmd_handler.execute("/tasks"))

    print("\n=== Testing Subagent Spawn ===")
    task_id = manager.spawn_subagent("Write a unit test for memory service", {"framework": "pytest"})
    print(f"Spawned subagent for task: {task_id}")
    import time

    time.sleep(1)  # wait for subagent to finish dummy execution

    print("\n[User Command] /tasks (After subagent spawn and completion)")
    print(cmd_handler.execute("/tasks"))

    print("\n=== Testing Verification Gate ===")
    try:
        manager.move_task(task_id, "DONE")
        print("ERROR: Should have failed verification gate!")
    except Exception as e:
        print(f"Expected Error Caught (Verification Gate): {e}")

    try:
        # 우회하여 kanban board에 직접 접근
        manager.kanban_board.move_task(task_id, "DONE", verification_note="All tests passed successfully.")
        print("Successfully moved task to DONE with verification_note.")
    except Exception as e:
        print(f"ERROR: Verification gate failed despite note: {e}")

    print("\n[User Command] /tasks (After Verification Gate)")
    print(cmd_handler.execute("/tasks"))

    print("\n=== Testing N:N Debate (MoE / Peer Review) ===")
    debate_topic = "How to implement efficient caching for the agent memory system?"
    final_result = manager.run_debate(
        topic=debate_topic, rounds=1, num_critics=2
    )  # 1 round for quick test with 2 critics
    print(f"Debate completed. Final Result Length: {len(final_result)}")
    print("Check data/artifacts folder for the debate_log file.")

    print("\n=== Memory Service Snapshot Retrieval ===")
    snapshot = memory.load_latest_snapshot("SYS")
    print(f"Latest SYS snapshot: {json.dumps(snapshot)}")

    print("\n=== Ssakfile Pro Multi-Agent System Test Completed ===")


if __name__ == "__main__":
    run_test()
