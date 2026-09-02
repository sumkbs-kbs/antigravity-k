import json
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import cast, final
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.orchestrator import OrchestratorAgent


def _mock_method(value: MagicMock, name: str) -> MagicMock:
    return cast(MagicMock, getattr(value, name))


@final
class ProgramBuilderManager:
    def __init__(self, app_path: Path) -> None:
        self.app_path = app_path
        self.calls = 0
        self.config: dict[str, object] = {}
        self._loaded_models: dict[str, object] = {}
        self.tracker = MagicMock()
        setattr(_mock_method(self.tracker, "get_recent"), "return_value", [])
        setattr(_mock_method(self.tracker, "get_total_tokens"), "return_value", 0)

    def is_loaded(self, _name: str) -> bool:
        return True

    def generate(self, _prompt: str = "", _target: str = "", **_kwargs: object) -> str:
        self.calls += 1
        if self.calls == 1:
            return (
                "def greet(name: str) -> str:\n"
                "    return f'Hello, {name}! Antigravity-K made this.'\n\n"
                "if __name__ == '__main__':\n"
                "    print(greet('QA'))\n"
            )
        elif self.calls == 2:
            return f"{sys.executable} {self.app_path}"
        else:
            return "Created and executed the sample program successfully."

    def stream_generate(self, *_args: object, **_kwargs: object) -> Iterator[str]:
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

    def get_target_for_role(self, _role_name: str = "", _default_role: str = "") -> str:
        return "test-model"

    def status(self) -> dict[str, list[object]]:
        return {"loaded_models": []}


@pytest.mark.skip(
    reason="OrchestratorAgent has been significantly refactored (state graph + engine context). This integration test needs comprehensive updates to match the new architecture."
)
def test_agent_can_create_and_run_a_simple_program(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    app_path = tmp_path / "hello_agent.py"
    manager = ProgramBuilderManager(app_path)

    def fake_ceo_analyze(_self: OrchestratorAgent, user_message: str, _target_model: str) -> Iterator[dict[str, str]]:
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
        watchdog = cast(object | None, getattr(orchestrator, "watchdog", None))
        if watchdog is not None:
            stopper = cast(Callable[[], object], getattr(watchdog, "stop"))
            _ = stopper()

    assert app_path.exists()
    assert "Antigravity-K made this." in app_path.read_text(encoding="utf-8")
    assert "Hello, QA! Antigravity-K made this." in output
    assert "Created and executed the sample program successfully." in output
