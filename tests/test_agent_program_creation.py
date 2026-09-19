import json
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast, final
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.approval_manager import (
    ApprovalDecision,
    get_approval_manager,
    reset_approval_manager,
)
from antigravity_k.engine.orchestrator import OrchestratorAgent


@contextmanager
def _grant_always_allow(tool_names: tuple[str, ...]) -> Iterator[None]:
    """사용자가 이 도구들을 승인한 상태를 **제품의 승인 시스템**으로 만든다.

    승인 게이트를 끄는 것이 아니다 — 대시보드 승인 API 가 구동하는 싱글턴
    (`get_approval_manager`)에 '항상 허용'을 기록해, 실제 사용자가 '항상 허용'을
    누른 것과 같은 상태를 만든다. 나머지 게이트(보안 정책·위험 명령·경로 샌드박스)는
    그대로 남으므로, 이 컨텍스트는 *어떤 도구*를 허가할 뿐 *어떤 명령*도 허가하지 않는다.
    """
    manager = get_approval_manager()
    try:
        for name in tool_names:
            request = manager.request_approval(
                tool_name=name,
                tool_args={},
                description=f"test consent: {name}",
            )
            _ = manager.resolve(request.request_id, ApprovalDecision.ALWAYS_ALLOW)
        yield
    finally:
        # 싱글턴 상태를 테스트 간에 남기지 않는다.
        reset_approval_manager()


def _mock_method(value: MagicMock, name: str) -> MagicMock:
    return cast(MagicMock, getattr(value, name))


@final
class _StubRouter:
    """라우터 더블 — 이 테스트가 재는 것은 모델 선택이 아니라 도구 루프이므로
    어떤 이름도 콤보로 판정하지 않는다(`get_combo` → None).

    툴 루프(`tool_loop.run_loop`)는 `manager.router.get_combo(...)` 를 무조건 호출해
    "콤보면 로드 여부 검사를 건너뛴다"를 판단한다 — 실제 `ModelManager` 는 생성자에서
    `self.router` 를 항상 만들므로(모델 없이도 존재), 더블도 같은 계약을 진다.
    """

    def get_combo(self, _name: str) -> None:
        return None


@final
class ProgramBuilderManager:
    def __init__(self, app_path: Path) -> None:
        self.app_path = app_path
        self.calls = 0
        self.config: dict[str, object] = {}
        self._loaded_models: dict[str, object] = {}
        self.router = _StubRouter()
        self.tracker = MagicMock()
        setattr(_mock_method(self.tracker, "get_recent"), "return_value", [])
        setattr(_mock_method(self.tracker, "get_total_tokens"), "return_value", 0)

    def is_loaded(self, _name: str) -> bool:
        return True

    def generate(self, _prompt: str = "", _target: str = "", **_kwargs: object) -> str:
        return next(self._turns(), "Created and executed the sample program successfully.")

    def _turns(self) -> Iterator[str]:
        """스크립트된 모델 턴 세 개: 파일 작성 → 프로그램 실행 → 최종 보고.

        실행 명령은 **프로젝트 루트 기준 상대 경로**로 쓴다. 셀 경로 경계(CR-04)는
        루트 밖 절대 경로(예: 저장소의 `sys.executable` — 테스트의 프로젝트 루트는
        tmp 디렉터리)를 정당하게 거부하므로, 여기서 그 경계를 우회하지 않는다.
        `cwd` 는 셀 도구에 대해 루트로 주입된다.
        """
        self.calls += 1
        if self.calls == 1:
            yield (
                "def greet(name: str) -> str:\n"
                "    return f'Hello, {name}! Ssak-Ai made this.'\n\n"
                "if __name__ == '__main__':\n"
                "    print(greet('QA'))\n"
            )
        elif self.calls == 2:
            yield f"python3 {self.app_path.name}"
        else:
            yield "Created and executed the sample program successfully."

    def stream_generate(self, *_args: object, **_kwargs: object) -> Iterator[str]:
        self.calls += 1
        if self.calls == 1:
            content = (
                "def greet(name: str) -> str:\n"
                "    return f'Hello, {name}! Ssak-Ai made this.'\n\n"
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
                        "command": f"python3 {self.app_path.name}",
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

    def get_model_info(self) -> dict[str, list[object]]:
        """`ModelManager.get_model_info` 는 `status()` 의 별칭이며 **인자를 받지 않는다**
        (`self_capability._model_info` 가 인자 없이 호출한다).
        """
        return self.status()


def test_agent_can_create_and_run_a_simple_program(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
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

    with _grant_always_allow(("write_file", "run_bash_command")):
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
    assert "Ssak-Ai made this." in app_path.read_text(encoding="utf-8")
    assert "Hello, QA! Ssak-Ai made this." in output
    assert "Created and executed the sample program successfully." in output
