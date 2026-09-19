"""MemoryRecorder 회귀 테스트.

record()가 preferred_model 인자를 존중하는지 검증합니다:
- preferred_model이 주어지면 정제 LLM 호출 target으로 그 모델을 사용
- None이면 기본 역할 모델(_get_model("default")) 사용
"""

from collections.abc import Iterator
from typing import final

from antigravity_k.engine.memory_recorder import MemoryRecorder


@final
class FakeVault:
    sync_rag: bool = True

    def __init__(self):
        self.write_calls: list[dict[str, object]] = []

    def write_note(self, **kwargs: object) -> None:
        self.write_calls.append(kwargs)


@final
class FakeManager:
    def __init__(self):
        self.stream_calls: list[dict[str, object]] = []

    def stream_generate(
        self,
        prompt: str,
        target: str,
        raw_messages: list[dict[str, str]],
        system_prompt: str,
    ) -> Iterator[str]:
        self.stream_calls.append(
            {
                "prompt": prompt,
                "target": target,
                "raw_messages": raw_messages,
                "system_prompt": system_prompt,
            },
        )
        return iter(["## Lessons Learned\n- 정제된 요약"])


def _get_model_fn(role: str) -> str:
    _ = role
    return "default-role-model"


def test_record_uses_preferred_model_when_provided():
    vault = FakeVault()
    manager = FakeManager()
    recorder = MemoryRecorder(vault, manager, _get_model_fn)

    _ = list(
        recorder.record(
            user_message="작업 요청",
            agent_output="작업 결과",
            task_type="coding",
            preferred_model="qwen3.6:latest",
        ),
    )

    assert manager.stream_calls, "stream_generate가 호출되어야 합니다"
    assert manager.stream_calls[0]["target"] == "qwen3.6:latest"
    assert vault.write_calls, "write_note가 호출되어야 합니다"


def test_record_falls_back_to_default_role_model_without_preference():
    vault = FakeVault()
    manager = FakeManager()
    recorder = MemoryRecorder(vault, manager, _get_model_fn)

    _ = list(
        recorder.record(
            user_message="작업 요청",
            agent_output="작업 결과",
            task_type="coding",
        ),
    )

    assert manager.stream_calls, "stream_generate가 호출되어야 합니다"
    assert manager.stream_calls[0]["target"] == "default-role-model"
    assert vault.write_calls, "write_note가 호출되어야 합니다"
