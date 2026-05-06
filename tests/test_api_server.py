import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from antigravity_k.api.server import app
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.protocol_translator import ProtocolTranslator


@pytest.fixture
def mock_manager():
    manager = MagicMock(spec=ModelManager)
    # generate 메서드가 성공적으로 문자열을 반환하도록 설정
    manager.generate.return_value = "This is a mock response from the LLM."
    return manager


@pytest.fixture
def mock_translator():
    # 실제 ProtocolTranslator를 사용하거나 Mocking
    return ProtocolTranslator()


@pytest.fixture
def client(mock_manager, mock_translator):
    # Dependency Injection 덮어쓰기
    from antigravity_k.api import dependencies

    app.dependency_overrides[dependencies.get_model_manager] = lambda: mock_manager
    app.dependency_overrides[dependencies.get_translator] = lambda: mock_translator

    with TestClient(app) as c:
        yield c

    app.dependency_overrides.clear()


def test_health_check(client):
    response = client.get("/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "backends": []}


def test_health_check_root_alias(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "backends": []}


def test_chat_completions_openai_format(client, mock_manager):
    payload = {
        "model": "test-combo",
        "messages": [{"role": "user", "content": "Hello, Antigravity!"}],
        "temperature": 0.8,
    }

    response = client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    data = response.json()

    # OpenAI 응답 구조 확인
    assert "id" in data
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) > 0
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert (
        data["choices"][0]["message"]["content"]
        == "This is a mock response from the LLM."
    )
    assert "usage" in data

    # ModelManager.generate 호출 확인
    mock_manager.generate.assert_called_once()
    kwargs = mock_manager.generate.call_args.kwargs
    assert kwargs["target"] == "test-combo"
    assert kwargs["temperature"] == 0.8
    # Prompt string 확인 (간단하게 포함 여부만)
    assert "Hello, Antigravity!" in kwargs["prompt"]


def test_chat_completions_routes_slash_goal(client, mock_manager):
    from antigravity_k.api.routes import legacy

    legacy._slash_registry = None
    payload = {
        "model": "test-combo",
        "messages": [
            {"role": "user", "content": "/goal DOM 기능을 테스트하고 리포트를 작성해줘"}
        ],
    }

    response = client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    data = response.json()
    content = data["choices"][0]["message"]["content"]
    assert "/goal Autonomous Goal Contract" in content
    assert "Autonomous Judgment Policy" in content
    assert "Autonomous Loop" in content
    mock_manager.generate.assert_not_called()


def test_embeddings_endpoint_uses_local_fallback(client):
    payload = {"model": "test-embed-model", "input": "Hello, embeddings!"}

    response = client.post("/v1/embeddings", json=payload)

    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert data["model"] == "test-embed-model"
    assert len(data["data"]) == 1
    assert len(data["data"][0]["embedding"]) == 1536
    assert data["usage"]["total_tokens"] > 0
