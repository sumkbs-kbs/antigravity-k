import asyncio
from antigravity_k.engine.orchestrator import OrchestratorAgent
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.model_registry import ModelRegistry


def main():
    registry = ModelRegistry()
    manager = ModelManager(registry)
    agent = OrchestratorAgent(manager)
    messages = [
        {
            "role": "user",
            "content": "Please run the command 'non_existent_command_xyz_888' using run_bash_command.",
        }
    ]

    print("Starting Orchestrator...")
    for chunk in agent.run_stream(messages, target_model="default"):
        print(chunk, end="", flush=True)


if __name__ == "__main__":
    main()
