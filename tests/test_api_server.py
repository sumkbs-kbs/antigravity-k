import json
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.server import app
from antigravity_k.config import config
from antigravity_k.engine.model_manager import ModelManager
from antigravity_k.engine.protocol_translator import ProtocolTranslator
from antigravity_k.tools.permission_gate import Permission


@pytest.fixture
def mock_manager():
    manager = MagicMock(spec=ModelManager)
    # generate 메서드가 성공적으로 문자열을 반환하도록 설정
    manager.generate.return_value = "This is a mock response from the LLM."
    # status()가 딕셔너리를 반환하도록 설정 (health check 등에서 사용)
    manager.status.return_value = {"loaded_models": []}
    # SlashCommandRegistry가 model_manager.router를 참조한다
    manager.router = MagicMock()
    return manager


@pytest.fixture
def mock_translator():
    # 실제 ProtocolTranslator를 사용하거나 Mocking
    return ProtocolTranslator()


@pytest.fixture
def client(mock_manager, mock_translator):
    """FastAPI DI + legacy module의 get_model_manager를 함께 오버라이드.

    _get_slash_registry()가 get_model_manager()를 직접 호출할 때도
    mock_manager가 반환되도록 legacy 모듈에도 패치를 적용합니다.
    """
    from antigravity_k.api import dependencies

    app.dependency_overrides[dependencies.get_model_manager] = lambda: mock_manager
    app.dependency_overrides[dependencies.get_translator] = lambda: mock_translator

    # legacy._get_slash_registry()가 직접 호출하는 get_model_manager도 오버라이드
    with patch("antigravity_k.api.dependencies.get_model_manager", return_value=mock_manager):
        with TestClient(app) as c:
            if config.security.access_pin:
                c.headers.update({"X-Access-Pin": config.security.access_pin})
            # Fixture 멤버 초기화 중 발생한 호출 기록 제거
            mock_manager.reset_mock()
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


def test_dashboard_spa_deep_link_serves_index(client):
    response = client.get("/agent")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "<html" in response.text.lower()


def test_api_routes_require_access_pin_without_auth_header():
    if not config.security.access_pin:
        pytest.skip("Access PIN is disabled for this environment")

    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.post("/api/slash", json={"input": "/goal test"})

    assert response.status_code == 401
    assert response.json()["ok"] is False


def test_memory_purge_requires_access_pin_without_auth_header():
    if not config.security.access_pin:
        pytest.skip("Access PIN is disabled for this environment")

    with TestClient(app) as unauthenticated_client:
        response = unauthenticated_client.request("DELETE", "/api/memory", json={"scope": "all"})

    assert response.status_code == 401


def test_skill_publish_github_honors_permission_denial_before_publisher_start(client, monkeypatch):
    from antigravity_k.api.routes import system_api

    gate = MagicMock()
    gate.check.return_value = Permission.DENY
    monkeypatch.setattr(system_api, "_permission_gate", lambda: gate, raising=False)

    response = client.post(
        "/api/system/skills/publish-github",
        json={"skill_name": "demo", "repo": "org/repo"},
    )

    assert response.status_code == 403


def test_skill_publish_npm_honors_permission_denial_before_publisher_start(client, monkeypatch):
    from antigravity_k.api.routes import system_api

    gate = MagicMock()
    gate.check.return_value = Permission.DENY
    monkeypatch.setattr(system_api, "_permission_gate", lambda: gate)

    response = client.post(
        "/api/system/skills/publish-npm",
        json={"skill_name": "demo"},
    )

    assert response.status_code == 403


def test_env_settings_honors_permission_denial_before_file_write(client, monkeypatch):
    from antigravity_k.api.routes import system_api as legacy

    gate = MagicMock()
    gate.check.return_value = Permission.DENY
    monkeypatch.setattr(legacy, "_permission_gate", lambda: gate, raising=False)
    monkeypatch.setattr("builtins.open", MagicMock())

    response = client.post(
        "/api/settings/env",
        json={"OPENAI_API_KEY": "redacted"},
    )

    assert response.status_code == 403


def test_env_settings_rejects_non_object_payload(client):
    response = client.post("/api/settings/env", json=[])

    assert response.status_code == 400


def test_env_settings_rejects_non_string_value(client):
    response = client.post("/api/settings/env", json={"OPENAI_API_KEY": 123})

    assert response.status_code == 400


def test_kanban_tasks_are_project_scoped_cancelled_and_removable(client):
    from antigravity_k.api.routes import kanban_api as legacy

    original_tasks = list(legacy.kanban_tasks)
    original_counter = legacy.task_counter
    legacy.kanban_tasks.clear()
    legacy.task_counter = 9100

    try:
        alpha = client.post(
            "/api/kanban/tasks",
            json={
                "description": "Alpha project task",
                "assignee": "QA",
                "workspace": "/tmp/antigravity-alpha",
            },
        )
        beta = client.post(
            "/api/kanban/tasks",
            json={
                "description": "Beta project task",
                "assignee": "WORKER",
                "workspace": "/tmp/antigravity-beta",
            },
        )

        assert alpha.status_code == 200
        assert beta.status_code == 200
        assert alpha.json()["project_name"] == "antigravity-alpha"
        assert beta.json()["project_name"] == "antigravity-beta"

        scoped = client.get("/api/kanban/tasks", params={"workspace": "/tmp/antigravity-alpha"})
        assert scoped.status_code == 200
        scoped_tasks = scoped.json()["data"]
        assert [task["title"] for task in scoped_tasks] == ["Alpha project task"]

        cancel = client.post(f"/api/kanban/tasks/{alpha.json()['id']}/cancel")
        assert cancel.status_code == 200
        assert cancel.json()["task"]["status"] == "cancelled"

        remove = client.delete(f"/api/kanban/tasks/{alpha.json()['id']}")
        assert remove.status_code == 200
        assert remove.json()["ok"] is True

        scoped_after_remove = client.get("/api/kanban/tasks", params={"workspace": "/tmp/antigravity-alpha"})
        assert scoped_after_remove.status_code == 200
        assert scoped_after_remove.json()["data"] == []
    finally:
        legacy.kanban_tasks.clear()
        legacy.kanban_tasks.extend(original_tasks)
        legacy.task_counter = original_counter


def test_kanban_websocket_sends_flat_tasks_payload(client):
    from antigravity_k.api.routes import kanban_api as legacy

    original_tasks = list(legacy.kanban_tasks)
    legacy.kanban_tasks.clear()
    legacy.kanban_tasks.append(
        {
            "id": "T-WS",
            "title": "WebSocket payload task",
            "description": "WebSocket payload task",
            "role": "QA",
            "status": "todo",
            "project_path": "/tmp/antigravity-ws",
            "project_name": "antigravity-ws",
        },
    )

    try:
        # WebSocket requires auth via query param (browsers can't set WS headers).
        # The client fixture sets X-Access-Pin for HTTP, but WS needs ?pin=.
        ws_url = "/ws/kanban"
        pin = config.security.access_pin
        if pin:
            ws_url += f"?pin={pin}"
        with client.websocket_connect(ws_url) as websocket:
            payload = json.loads(websocket.receive_text())

        assert "tasks" in payload
        assert payload["tasks"][0]["id"] == "T-WS"
        assert payload["todo"][0]["id"] == "T-WS"
        assert payload["BACKLOG"][0]["id"] == "T-WS"
    finally:
        legacy.kanban_tasks.clear()
        legacy.kanban_tasks.extend(original_tasks)


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
    assert data["choices"][0]["message"]["content"] == "This is a mock response from the LLM."
    assert "usage" in data

    # ModelManager.generate 호출 확인 (intent classifier 1회 + 실제 생성 1회)
    assert mock_manager.generate.call_count == 2
    # 실제 생성 호출(두 번째 호출)의 kwargs 검증
    kwargs = mock_manager.generate.call_args_list[1].kwargs
    assert kwargs["target"] == "test-combo"
    assert kwargs["temperature"] == 0.8
    # Prompt string 확인 (간단하게 포함 여부만)
    assert "Hello, Antigravity!" in kwargs["prompt"]


@pytest.mark.parametrize(
    "payload",
    [
        [],
        {"model": 123, "messages": []},
        {"model": "test-combo", "messages": "not-an-array"},
        {"model": "test-combo", "messages": [None]},
        {"model": "test-combo", "messages": [{"role": 1, "content": "hello"}]},
        {"model": "test-combo", "messages": [{"role": "user", "content": ["hello"]}]},
        {"model": "test-combo", "messages": [], "stream": "false"},
    ],
)
def test_chat_completions_rejects_malformed_payload(client, payload):
    response = client.post("/v1/chat/completions", json=payload)

    assert response.status_code == 400


def test_chat_completions_rejects_malformed_json(client):
    response = client.post("/v1/chat/completions", content="{")

    assert response.status_code == 400


@pytest.mark.parametrize("payload", [[], {"name": 123}, {"name": "test-combo", "role": 123}])
def test_set_default_model_rejects_malformed_payload(client, payload):
    response = client.post("/api/models/default", json=payload)

    assert response.status_code == 400


def test_set_default_model_rejects_malformed_json(client):
    response = client.post("/api/models/default", content="{")

    assert response.status_code == 400


def test_chat_reconnect_endpoint_uses_shared_session_state(client):
    from antigravity_k.api.routes.session_state import reset_active_session

    reset_active_session()

    response = client.get("/v1/chat/completions/reconnect")

    assert response.status_code == 200
    assert "data: [DONE]" in response.text


def test_chat_completions_routes_slash_goal(client, mock_manager):
    import antigravity_k.api.dependencies as deps

    deps._slash_registry = None
    payload = {
        "model": "test-combo",
        "messages": [{"role": "user", "content": "/goal DOM 기능을 테스트하고 리포트를 작성해줘"}],
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
    import antigravity_k.api.dependencies as deps

    deps._slash_registry = None
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
    import antigravity_k.api.dependencies as deps

    deps._slash_registry = None
    payload = {
        "model": "test-combo",
        "messages": [
            {
                "role": "user",
                "content": "/codex DOM 테스트와 제로 오류 정책을 업그레이드해줘",
            },
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
            },
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
    import antigravity_k.api.dependencies as deps

    deps._slash_registry = None

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
    import antigravity_k.api.dependencies as deps

    deps._slash_registry = None

    response = client.post("/api/slash", json={})

    assert response.status_code == 200
    data = response.json()
    assert data == {"ok": True, "result": "Error: Empty command."}
    mock_manager.generate.assert_not_called()


def test_slash_api_benchmark_help_returns_plain_text(client, mock_manager):
    import antigravity_k.api.dependencies as deps

    deps._slash_registry = None

    response = client.post("/api/slash", json={"input": "/benchmark"})

    assert response.status_code == 200
    data = response.json()
    assert data["ok"] is True
    assert isinstance(data["result"], str)
    assert "Benchmark 명령어" in data["result"]
    mock_manager.generate.assert_not_called()


def test_task_benchmark_api_submits_a_canonical_scenario(client, monkeypatch):
    from antigravity_k.api.routes import task_api

    runtime = MagicMock()
    runtime.submit_task.return_value = "task_benchmark_001"
    monkeypatch.setattr(task_api, "get_agent_runtime", lambda: runtime)

    response = client.post(
        "/api/tasks/benchmark/srch-002",
        json={"model": "qwen3.6:latest", "idempotency_key": "benchmark-srch-002"},
    )

    assert response.status_code == 200
    assert response.json()["benchmark_case"]["id"] == "srch-002"
    submitted = runtime.submit_task.call_args.kwargs
    assert submitted["target_model"] == "qwen3.6:latest"
    assert submitted["idempotency_key"] == "benchmark-srch-002"
    assert submitted["context"]["benchmark_case_id"] == "srch-002"
    assert submitted["context"]["expected_tools"] == ["web_search"]
    assert submitted["context"]["expected_keywords"]
    assert submitted["context"]["benchmark_read_only"] is True


def test_task_cancel_api_cancels_background_task(client, monkeypatch):
    from antigravity_k.api.routes import task_api

    runtime = MagicMock()
    runtime.cancel_task.return_value = True
    monkeypatch.setattr(task_api, "get_agent_runtime", lambda: runtime)

    response = client.post("/api/tasks/task_123/cancel")

    assert response.status_code == 200
    assert response.json() == {"status": "cancelled", "task_id": "task_123"}
    runtime.cancel_task.assert_called_once_with("task_123", owner_subject="loopback")


def test_task_cancel_api_rejects_unknown_or_terminal_task(client, monkeypatch):
    from antigravity_k.api.routes import task_api

    runtime = MagicMock()
    runtime.cancel_task.return_value = False
    monkeypatch.setattr(task_api, "get_agent_runtime", lambda: runtime)

    response = client.post("/api/tasks/task_missing/cancel")

    assert response.status_code == 404
    assert response.json()["detail"] == "Task is not active"


def test_task_api_reads_and_resumes_direct_task_through_canonical_runtime(client, monkeypatch):
    from antigravity_k.api.routes import task_api

    runtime = MagicMock()
    runtime.get_task_status.return_value = {"task_id": "direct_001", "status": "failed"}
    runtime.list_tasks.return_value = [{"task_id": "direct_001", "status": "failed"}]
    runtime.get_task_output.return_value = "partial-output"
    runtime.resume_task.return_value = True
    monkeypatch.setattr(task_api, "get_agent_runtime", lambda: runtime)

    status = client.get("/api/tasks/direct_001/status")
    tasks = client.get("/api/tasks?limit=1")
    output = client.get("/api/tasks/direct_001/output")
    resumed = client.post("/api/tasks/direct_001/resume")

    assert status.json()["data"] == {"task_id": "direct_001", "status": "failed"}
    assert tasks.json()["data"] == [{"task_id": "direct_001", "status": "failed"}]
    assert output.json() == {"status": "ok", "task_id": "direct_001", "output": "partial-output"}
    assert resumed.json() == {"status": "resumed", "task_id": "direct_001"}
    runtime.get_task_status.assert_called_once_with("direct_001", owner_subject="loopback")
    runtime.list_tasks.assert_called_once_with(limit=1, owner_subject="loopback")
    runtime.get_task_output.assert_called_once_with("direct_001", owner_subject="loopback")


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
