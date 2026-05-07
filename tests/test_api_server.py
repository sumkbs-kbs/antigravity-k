import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock

from antigravity_k.api.server import app
from antigravity_k.config import config
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
        if config.security.access_pin:
            c.headers.update({"X-Access-Pin": config.security.access_pin})
        yield c

    app.dependency_overrides.clear()


def test_health_check(client):
    response = client.get("/v1/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["backends"] == []
    assert "rag_index_files" in data
    assert "cov_active" in data


def test_health_check_root_alias(client):
    response = client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["backends"] == []
    assert "rag_index_files" in data
    assert "cov_active" in data


def test_api_routes_require_access_pin_without_auth_header():
    if not config.security.access_pin:
        pytest.skip("Access PIN is disabled for this environment")

    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.post(
            "/api/slash", json={"input": "/goal test"}
        )

    assert response.status_code == 401
    assert response.json()["ok"] is False


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


def test_chat_completions_capabilities_uses_connected_policy(client, mock_manager):
    from antigravity_k.api.routes import legacy

    legacy._slash_registry = None
    payload = {
        "model": "test-combo",
        "messages": [{"role": "user", "content": "/capabilities DOM browser testing"}],
    }

    response = client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert "Autonomous Capability Manifest" in content
    assert "Autonomous Capability Policy" in content
    assert content.count("Autonomous Capability Policy") == 1
    assert "**Tools/MCP:** allow=" in content
    assert "Tool registry not connected" not in content
    assert "Skill loader not connected" not in content
    mock_manager.generate.assert_not_called()


def test_chat_completions_routes_slash_codex(client, mock_manager):
    from antigravity_k.api.routes import legacy

    legacy._slash_registry = None
    payload = {
        "model": "test-combo",
        "messages": [
            {
                "role": "user",
                "content": "/codex DOM 테스트와 제로 오류 정책을 업그레이드해줘",
            }
        ],
    }

    response = client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert "Codex Capability Transfer Manifest" in content
    assert "Zero-Error Completion Gates" in content
    assert "Autonomous Tool Judgment" in content
    assert "Private model weights" in content
    mock_manager.generate.assert_not_called()


def test_chat_completions_self_capability_bypasses_llm(client, mock_manager):
    payload = {
        "model": "test-combo",
        "messages": [
            {
                "role": "user",
                "content": "너를 소개하고 니가 할 수 있는 일과 할 수 없는 일을 알려줘",
            }
        ],
    }

    response = client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 200
    content = response.json()["choices"][0]["message"]["content"]
    assert "Antigravity-K Self Capability Report" in content
    assert "현재 런타임에 등록되지 않은 도구" in content
    assert "등록 도구" in content
    mock_manager.generate.assert_not_called()


def test_slash_api_accepts_input_alias(client, mock_manager):
    from antigravity_k.api.routes import legacy

    legacy._slash_registry = None

    response = client.post(
        "/api/slash",
        json={"input": "/goal 출력 품질을 Codex 수준으로 개선해줘"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert "/goal Autonomous Goal Contract" in data["result"]
    assert "Response quality gates" in data["result"]
    mock_manager.generate.assert_not_called()


def test_slash_api_empty_command_returns_structured_error(client, mock_manager):
    from antigravity_k.api.routes import legacy

    legacy._slash_registry = None

    response = client.post("/api/slash", json={})

    assert response.status_code == 200
    data = response.json()
    assert data == {"ok": True, "result": "Error: Empty command."}
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
