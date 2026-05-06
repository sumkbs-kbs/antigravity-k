import json
import sys

from antigravity_k.engine.orchestrator import OrchestratorAgent


class ProgramBuilderManager:
    def __init__(self, app_path):
        self.app_path = app_path
        self.calls = 0

    def is_loaded(self, name):
        return True

    def stream_generate(self, *args, **kwargs):
        self.calls += 1
        if self.calls == 1:
            content = (
                "def greet(name: str) -> str:\n"
                "    return f'Hello, {name}! Antigravity-K made this.'\n\n"
                "if __name__ == '__main__':\n"
                "    print(greet('QA'))\n"
            )
            yield "<scratch_pad>create the requested sample program</scratch_pad>\n"
            yield "<tool_call>\n"
            yield json.dumps(
                {
                    "name": "write_file",
                    "arguments": {
                        "file_path": str(self.app_path),
                        "content": content,
                    },
                }
            )
            yield "\n</tool_call>"
        elif self.calls == 2:
            yield "<scratch_pad>run the generated program</scratch_pad>\n"
            yield "<tool_call>\n"
            yield json.dumps(
                {
                    "name": "run_bash_command",
                    "arguments": {
                        "command": f"{sys.executable} {self.app_path}",
                    },
                }
            )
            yield "\n</tool_call>"
        else:
            yield "Created and executed the sample program successfully."


def test_agent_can_create_and_run_a_simple_program(tmp_path, monkeypatch):
    app_path = tmp_path / "hello_agent.py"
    manager = ProgramBuilderManager(app_path)

    def fake_ceo_analyze(self, user_message, target_model):
        yield {
            "task_type": "coding",
            "delegate_to": "WORKER",
            "reasoning": "test program creation",
            "refined_prompt": user_message,
        }

    monkeypatch.setattr(OrchestratorAgent, "_ceo_analyze", fake_ceo_analyze)

    orchestrator = OrchestratorAgent(
        model_manager=manager,
        vault_engine=None,
        project_root=str(tmp_path),
    )
    try:
        output = "".join(
            orchestrator.run_stream(
                [
                    {
                        "role": "user",
                        "content": "간단한 인사 프로그램을 만들어 실행해줘.",
                    }
                ],
                target_model="test-model",
                max_steps=5,
            )
        )
    finally:
        if orchestrator.watchdog:
            orchestrator.watchdog.stop()

    assert app_path.exists()
    assert "Antigravity-K made this." in app_path.read_text(encoding="utf-8")
    assert "Hello, QA! Antigravity-K made this." in output
    assert "Created and executed the sample program successfully." in output
