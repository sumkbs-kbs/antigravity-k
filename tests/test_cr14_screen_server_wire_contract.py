"""F-37 · F-38 — 대시보드(화면)와 서버가 **같은 와이어**를 말하는지 고정한다.

왜 이 파일이 따로 있는가
------------------------
두 결함의 뿌리는 같다: 화면과 서버가 만나는 자리를 **재는 곳이 없었다**. 화면 쪽에는 그 본문을
고정하는 테스트가 하나도 없었고(`withProjectIdentityPayload` 를 쓰는 호출부 중 태스크 제출만
`context` 중첩을 요구하는 서버와 어긋났다), 서버 쪽 계약은 `context.project_id` 만 재고
**최상위 형태**(공유 리졸버 `extract_project_id_from_payload` 가 이미 지원하는 형태)는 재지 않았다.

  F-37  화면은 정체성을 **최상위** `project_id`(+`project_revision`)로 보내는데
        `TaskSubmitRequest` 는 `extra="forbid"` 라 그 본문을 **422** 로 막았다 — 화면의 유일한 쓰기
        경로("작업 제출")가 어떤 환경에서도 성공하지 못했다. (`extra` 를 풀어서가 아니라 **선언**해서
        고쳤다: 두 형태를 다 인정하되 모르는 필드는 계속 거부한다.)
  F-38  서버는 한 번도 열리지 않은 프로젝트를 `last_accessed_at: null` 로 직렬화하는데
        (`ProjectRecord.model_dump()`), 화면의 스키마(`z.string().optional()`)는 `null` 을 거부해
        목록 파싱이 실패했다 → 스토어가 비고 → 제출이 **정체성 없이** 나가 400
        `missing_execution_context`. (다른 끝은 `dashboard/src/api/contractAlignment.test.ts` 가
        실제 zod 로 고정한다 — 이 파일은 **서버가 무엇을 보내는가**를 고정한다.)

무엇을 재지 않는가
------------------
- **모델 실행**은 재지 않는다(가짜 런타임이 `submit_task` 인자를 기록한다).
- **화면 렌더링**은 재지 않는다(브라우저 증인이 판다: `dashboard/e2e/tests/cr14-task-submit-contract.spec.ts`).
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from antigravity_k.api.project_binding import (
    clear_runtime_captures,
    disable_runtime_capture,
    get_session_project_bindings,
    reset_bound_request_execution_context,
)
from antigravity_k.api.server import app

# 대시보드가 실제로 보내는 것과 **같은 자리**를 쓴다(`createProjectIdentityHeaders` +
# `withProjectIdentityPayload`): 정체성은 본문 최상위와 헤더 양쪽에 실린다.
IDENTITY_HEADERS = {"X-AGK-Session-Id": "default", "X-AGK-Project-Id": "default"}


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """격리된 레지스트리(빈 상태 → 기본 프로젝트)를 가진 TestClient."""
    from antigravity_k.config import config

    monkeypatch.setattr(
        "antigravity_k.engine.project_registry._DEFAULT_STORAGE_PATH",
        tmp_path / "projects.json",
    )
    import antigravity_k.engine.project_registry as preg

    monkeypatch.setattr(preg, "_global_registry", None)
    monkeypatch.setattr(config.paths, "project_root", tmp_path.resolve())
    monkeypatch.delenv("AGK_ALLOWED_ROOTS", raising=False)

    get_session_project_bindings().reset_all()
    clear_runtime_captures()
    disable_runtime_capture()
    reset_bound_request_execution_context()

    with TestClient(app, raise_server_exceptions=False) as test_client:
        test_client.headers.update({"X-Access-Pin": config.security.access_pin})
        yield test_client

    get_session_project_bindings().reset_all()
    clear_runtime_captures()
    disable_runtime_capture()
    reset_bound_request_execution_context()
    monkeypatch.setattr(preg, "_global_registry", None)


def _register_project(client: TestClient, name: str, path: Path) -> dict:
    """허용 뿌리 안의 실제 디렉터리를 등록한다(테스트 픽스처의 기본 프로젝트는 저장소 cwd 를 가리킨다)."""
    path.mkdir(parents=True, exist_ok=True)
    response = client.post("/api/projects", json={"name": name, "path": str(path)})
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["ok"] is True
    return data["project"]


class _RecordingRuntime:
    """`submit_task` 로 **무엇이 도착했는지**만 기록한다(모델은 돌리지 않는다)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, object]] = []

    def submit_task(self, **kwargs: object) -> str:
        self.calls.append(dict(kwargs))
        return "task_wire_1"

    def get_task_status(self, *args: object, **kwargs: object) -> None:
        return None


def _install(monkeypatch: pytest.MonkeyPatch) -> _RecordingRuntime:
    runtime = _RecordingRuntime()
    monkeypatch.setattr(
        "antigravity_k.api.routes.task_api._runtime",
        lambda: runtime,
    )
    return runtime


def test_submit_accepts_the_identity_form_the_dashboard_sends(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """F-37: 화면의 본문(최상위 `project_id` + `project_revision`)이 **202** 로 접수된다."""
    alpha = _register_project(client, "Alpha", tmp_path / "alpha")
    runtime = _install(monkeypatch)
    project_id = str(alpha["id"])

    response = client.post(
        "/api/tasks/submit",
        json={"prompt": "화면이 보내는 그대로", "project_id": project_id, "project_revision": 0},
        headers={**IDENTITY_HEADERS, "X-AGK-Project-Id": project_id},
    )

    assert response.status_code == 202, response.text
    assert runtime.calls, "제출이 런타임에 도착하지 않았다"
    context = runtime.calls[0]["context"]
    assert isinstance(context, dict)
    # "수용했다"가 아니라 **정체성이 도착했다**: 불변 프로젝트 결속이 컨텍스트에 실려야 한다.
    assert context.get("project_id") == project_id
    assert context.get("canonical_project_root")
    assert isinstance(context.get("execution_context"), dict)


def test_submit_reads_the_top_level_project_id(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    """이빨: 최상위 `project_id` 가 **읽히는가** — 등록되지 않은 프로젝트면 202 가 아니라 404 다.

    이 검사가 없으면 "수용했다"가 "값을 읽었다"를 뜻하지 않는다: 필드가 조용히 버려져도
    세션 바인딩(또는 기본 프로젝트)으로 202 가 나올 수 있다.
    """
    runtime = _install(monkeypatch)

    response = client.post(
        "/api/tasks/submit",
        json={"prompt": "유령 프로젝트", "project_id": "no-such-project"},
        headers=IDENTITY_HEADERS,
    )

    assert response.status_code == 404, response.text
    assert response.json().get("error") == "project_not_found"
    assert runtime.calls == []


def test_submit_prefers_the_nested_identity_over_the_top_level_one(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """두 자리가 다 있으면 더 구체적인 `context.project_id` 가 이긴다(예전 동작 그대로)."""
    alpha = _register_project(client, "Alpha", tmp_path / "alpha")
    runtime = _install(monkeypatch)
    project_id = str(alpha["id"])

    response = client.post(
        "/api/tasks/submit",
        json={
            "prompt": "둘 다",
            "project_id": "no-such-project",
            "context": {"project_id": project_id},
        },
    )

    assert response.status_code == 202, response.text
    context = runtime.calls[0]["context"]
    assert isinstance(context, dict)
    assert context.get("project_id") == project_id


def test_submit_still_refuses_a_body_without_any_identity(client: TestClient) -> None:
    """경계는 그대로다: 정체성이 어디에도 없으면 202 가 아니다(조용한 기본값 금지)."""
    response = client.post("/api/tasks/submit", json={"prompt": "정체성 없는 요청"})

    assert response.status_code == 400, response.text
    assert response.json().get("error") == "missing_execution_context"


def test_submit_still_forbids_unknown_fields(client: TestClient) -> None:
    """`extra="forbid"` 는 살아 있다 — 두 형태를 **선언**했지 `extra` 를 푼 것이 아니다."""
    response = client.post(
        "/api/tasks/submit",
        json={"prompt": "모르는 필드", "project_id": "default", "nonsense": 1},
    )

    assert response.status_code == 422, response.text


def test_projects_payload_marks_a_never_opened_project_as_null(client: TestClient) -> None:
    """F-38 의 **서버 쪽 끝**: 한 번도 열리지 않은 프로젝트는 `last_accessed_at: null` 로 나간다.

    `ProjectRecord.model_dump()` 는 그 키를 **언제나** 포함한다(값이 없으면 `None`). 화면의 스키마가
    `null` 을 거부하면 목록 전체가 파싱에 실패하고, 화면은 자기 프로젝트를 잃는다 — 그래서 이 값은
    "서버가 이상하다"가 아니라 **서버의 정상 타입**이다(다른 끝: `contractAlignment.test.ts`).
    """
    response = client.get("/api/projects")

    assert response.status_code == 200, response.text
    payload = response.json()
    current = payload["current_project"]
    assert "last_accessed_at" in current, "키를 빼면 화면의 스키마가 그 사실을 알 수 없다"
    assert current["last_accessed_at"] is None
    never_opened = [row for row in payload["projects"] if row.get("last_accessed_at") is None]
    assert never_opened, "기본 프로젝트가 목록에 없으면 이 계약은 서버의 실제 모양을 재지 않는다"
