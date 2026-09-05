from pathlib import Path

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from antigravity_k.api.routes import voice_api
from antigravity_k.engine.scheduled_job_service import ScheduledJobService
from antigravity_k.engine.scheduled_job_store import ScheduledJobStore


class FakeVoiceService:
    def transcribe(self, audio: bytes, suffix: str) -> str:
        assert audio == b"audio-bytes"
        assert suffix == ".wav"
        return "오늘 할 일을 정리해줘"

    def synthesize(self, text: str) -> bytes:
        assert text == "완료했습니다"
        return b"aiff-bytes"


class FakeRuntime:
    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def submit_task(self, **kwargs: object) -> str:
        self.calls.append(kwargs)
        return "task-voice-1"

    def get_task_status(self, task_id: str) -> dict[str, object]:
        return {"task_id": task_id, "status": "done", "output": "voice result"}


@pytest.fixture
def runtime(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FakeRuntime:
    fake = FakeRuntime()
    jobs = ScheduledJobService(
        ScheduledJobStore(str(tmp_path / "jobs.db")),
        fake.submit_task,
        fake.get_task_status,
    )
    monkeypatch.setattr(voice_api, "get_voice_service", FakeVoiceService)
    monkeypatch.setattr(voice_api, "get_scheduled_job_service", lambda: jobs)
    return fake


@pytest.fixture
def client() -> TestClient:
    app = FastAPI()
    app.include_router(voice_api.router)
    return TestClient(app)


def test_voice_transcription_endpoint(client: TestClient, runtime: FakeRuntime) -> None:
    response = client.post(
        "/api/voice/transcribe?suffix=.wav",
        content=b"audio-bytes",
        headers={"Content-Type": "audio/wav"},
    )

    assert response.status_code == 200
    assert response.json() == {"transcript": "오늘 할 일을 정리해줘"}
    assert runtime.calls == []


def test_voice_command_submits_transcript_to_jarvis(client: TestClient, runtime: FakeRuntime) -> None:
    response = client.post(
        "/api/voice/commands?suffix=.wav&model=qwen3.8:27b",
        content=b"audio-bytes",
        headers={"Content-Type": "audio/wav"},
    )

    assert response.status_code == 202
    body = response.json()
    assert body["transcript"] == "오늘 할 일을 정리해줘"
    assert body["task_id"] == "task-voice-1"
    assert runtime.calls[0]["target_model"] == "qwen3.8:27b"


def test_voice_synthesis_returns_playable_audio(client: TestClient, runtime: FakeRuntime) -> None:
    response = client.post("/api/voice/speak", json={"text": "완료했습니다"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "audio/aiff"
    assert response.content == b"aiff-bytes"
    assert runtime.calls == []
