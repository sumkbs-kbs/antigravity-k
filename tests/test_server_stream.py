import json
from collections.abc import Iterator

import pytest

from antigravity_k.engine.orchestrator import OrchestratorAgent


class FakeManager:
    def is_loaded(self, _name: str) -> bool:
        return True

    def stream_generate(self, *_args: object, **_kwargs: object) -> Iterator[str]:
        yield "stream chunk"


def test_orchestrator_stream_chunks_can_be_serialized(monkeypatch: pytest.MonkeyPatch):
    def fake_ceo_analyze(
        _self: OrchestratorAgent,
        user_message: str,
        _target_model: str,
    ) -> Iterator[dict[str, str]]:
        yield {
            "task_type": "simple_chat",
            "delegate_to": "SELF",
            "reasoning": "test",
            "refined_prompt": user_message,
        }

    monkeypatch.setattr(OrchestratorAgent, "_ceo_analyze", fake_ceo_analyze)

    orchestrator = OrchestratorAgent(model_manager=FakeManager(), vault_engine=None)
    messages = [{"role": "user", "content": "간단히 응답해줘"}]

    chunks = list(orchestrator.run_stream(messages, target_model="test-model", max_steps=1))

    assert chunks
    sse_payloads = [
        {
            "id": "chatcmpl-stream",
            "object": "chat.completion.chunk",
            "model": "test-model",
            "choices": [{"delta": {"content": chunk}, "index": 0, "finish_reason": None}],
        }
        for chunk in chunks
    ]

    for payload in sse_payloads:
        encoded = f"data: {json.dumps(payload)}\n\n"
        assert encoded.startswith("data: ")
