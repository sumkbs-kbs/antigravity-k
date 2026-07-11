import json

from antigravity_k.engine.orchestrator import OrchestratorAgent


class FakeManager:
    def is_loaded(self, name):
        return True

    def stream_generate(self, *args, **kwargs):
        yield "stream chunk"


def test_orchestrator_stream_chunks_can_be_serialized(monkeypatch):
    def fake_ceo_analyze(self, user_message, target_model):
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
