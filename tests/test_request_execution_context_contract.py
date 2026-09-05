"""ARC-01 frozen RequestExecutionContext + conversation revision contracts.

WS-01 / CTX-01 lanes must consume these types and error codes without redefining
them. Fixtures live in tests/fixtures/commercial_ga/.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from antigravity_k.api.contracts import (
    CONTEXT_ERROR_HTTP_STATUS,
    REQUEST_EXECUTION_CONTEXT_SCHEMA_VERSION,
    ConversationConflictPayload,
    ConversationSnapshot,
    MissingExecutionContextError,
    ProjectNotFoundError,
    ProjectRootInvalidError,
    RequestExecutionContext,
    RequestExecutionContextWire,
    StaleConversationRevisionError,
)
from antigravity_k.api.contracts.errors import execution_context_error_from_code
from antigravity_k.engine.project_registry import ProjectRegistry
from antigravity_k.engine.request_execution_context import (
    InMemoryConversationRevisionStore,
    reject_raw_path_authority,
    resolve_canonical_project_root,
    resolve_request_execution_context,
)

FIXTURE_PATH = Path(__file__).parent / "fixtures" / "commercial_ga" / "arc01_request_execution_context.json"
DASHBOARD_FIXTURE = (
    Path(__file__).resolve().parents[1]
    / "dashboard"
    / "src"
    / "api"
    / "fixtures"
    / "arc01_request_execution_context.json"
)


@pytest.fixture(scope="module")
def fixture_doc() -> dict:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def test_python_and_dashboard_fixtures_are_byte_identical() -> None:
    assert FIXTURE_PATH.is_file()
    assert DASHBOARD_FIXTURE.is_file()
    assert FIXTURE_PATH.read_bytes() == DASHBOARD_FIXTURE.read_bytes()


def test_fixture_error_http_status_matches_python_contract(fixture_doc: dict) -> None:
    assert fixture_doc["error_http_status"] == CONTEXT_ERROR_HTTP_STATUS
    assert fixture_doc["schema_version"] == REQUEST_EXECUTION_CONTEXT_SCHEMA_VERSION


def test_wire_example_parses_and_forbids_extra_fields(fixture_doc: dict) -> None:
    wire = RequestExecutionContextWire.model_validate(fixture_doc["wire_example"])
    assert wire.project_id == "proj_arc01_alpha"
    assert wire.client_hint_path == "/tmp/client-hint-must-be-ignored"
    with pytest.raises(Exception):
        RequestExecutionContextWire.model_validate({**fixture_doc["wire_example"], "path": "/evil"})


def test_resolved_context_is_immutable(fixture_doc: dict, tmp_path: Path) -> None:
    root = tmp_path / "alpha"
    root.mkdir()
    registry = ProjectRegistry(storage_path=tmp_path / "projects.json")
    # replace default with known id
    record = registry.add_project(name="ARC-01 Alpha", path=str(root))
    # Force stable id used by fixture by re-seeding storage
    data = json.loads((tmp_path / "projects.json").read_text(encoding="utf-8"))
    for item in data:
        if item["id"] == record.id:
            item["id"] = "proj_arc01_alpha"
            item["name"] = "ARC-01 Alpha"
            item["path"] = str(root.resolve())
    (tmp_path / "projects.json").write_text(json.dumps(data), encoding="utf-8")
    registry = ProjectRegistry(storage_path=tmp_path / "projects.json")

    store = InMemoryConversationRevisionStore()
    store.seed(project_id="proj_arc01_alpha", conversation_id="conv_arc01_001", revision=3)

    wire = RequestExecutionContextWire.model_validate(fixture_doc["wire_example"])
    ctx = resolve_request_execution_context(wire, registry=registry, conversation_store=store)

    assert isinstance(ctx, RequestExecutionContext)
    assert ctx.project_id == "proj_arc01_alpha"
    assert Path(ctx.canonical_project_root) == root.resolve()
    assert ctx.canonical_project_root.startswith("/")
    assert ctx.conversation_revision == 3
    assert ctx.model_config.get("frozen") is True
    with pytest.raises(Exception):
        ctx.project_id = "mutated"  # type: ignore[misc]


def test_client_hint_path_is_not_authority(fixture_doc: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "alpha"
    root.mkdir()
    other = tmp_path / "other"
    other.mkdir()
    registry = ProjectRegistry(storage_path=tmp_path / "projects.json")
    registry.add_project(name="Alpha", path=str(root))
    # rename id
    data = json.loads((tmp_path / "projects.json").read_text(encoding="utf-8"))
    pid = data[-1]["id"] if data else "default"
    for item in data:
        if item["path"] == str(Path(root).resolve()) or item["path"] == str(root):
            item["id"] = "proj_arc01_alpha"
            pid = "proj_arc01_alpha"
    (tmp_path / "projects.json").write_text(json.dumps(data), encoding="utf-8")
    registry = ProjectRegistry(storage_path=tmp_path / "projects.json")

    from antigravity_k.config import config

    monkeypatch.setattr(config.paths, "project_root", root.resolve())

    wire = RequestExecutionContextWire.model_validate(
        {
            **fixture_doc["wire_example"],
            "project_id": pid,
            "client_hint_path": str(other),
        }
    )
    store = InMemoryConversationRevisionStore()
    store.seed(project_id=pid, conversation_id="conv_arc01_001", revision=3)
    ctx = resolve_request_execution_context(wire, registry=registry, conversation_store=store)
    assert Path(ctx.canonical_project_root) == root.resolve()
    assert Path(ctx.canonical_project_root) != other.resolve()


def test_missing_project_raises_typed_404(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    registry = ProjectRegistry(storage_path=tmp_path / "projects.json")
    monkeypatch.setattr(
        "antigravity_k.config.config.paths.project_root",
        tmp_path.resolve(),
    )
    with pytest.raises(ProjectNotFoundError) as excinfo:
        resolve_canonical_project_root("does-not-exist", registry=registry)
    assert excinfo.value.status_code == 404
    assert excinfo.value.error_code == "project_not_found"


def test_invalid_root_directory_raises_403(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    missing = tmp_path / "gone"
    registry = ProjectRegistry(storage_path=tmp_path / "projects.json")
    # inject a record pointing at a non-existent path
    registry._projects["proj_missing"] = registry.get_active_project().__class__(
        id="proj_missing",
        name="Missing",
        path=str(missing),
        is_active=False,
    )
    monkeypatch.setattr(
        "antigravity_k.config.config.paths.project_root",
        tmp_path.resolve(),
    )
    # allowlist includes tmp_path so resolve_allowed_path can accept child
    with pytest.raises(ProjectRootInvalidError) as excinfo:
        resolve_canonical_project_root("proj_missing", registry=registry)
    assert excinfo.value.status_code == 403
    assert excinfo.value.error_code == "project_root_invalid"


def test_stale_conversation_revision_raises_409(
    fixture_doc: dict, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "alpha"
    root.mkdir()
    registry = ProjectRegistry(storage_path=tmp_path / "projects.json")
    rec = registry.add_project(name="Alpha", path=str(root))
    monkeypatch.setattr(
        "antigravity_k.config.config.paths.project_root",
        root.resolve(),
    )
    store = InMemoryConversationRevisionStore()
    store.seed(project_id=rec.id, conversation_id="conv_arc01_001", revision=4)
    wire = RequestExecutionContextWire.model_validate(
        {**fixture_doc["wire_example"], "project_id": rec.id, "conversation_revision": 3}
    )
    with pytest.raises(StaleConversationRevisionError) as excinfo:
        resolve_request_execution_context(wire, registry=registry, conversation_store=store)
    assert excinfo.value.status_code == 409
    assert excinfo.value.context["current_revision"] == 4


def test_missing_wire_raises_400() -> None:
    with pytest.raises(MissingExecutionContextError) as excinfo:
        resolve_request_execution_context(None)
    assert excinfo.value.status_code == 400


def test_reject_raw_path_authority() -> None:
    with pytest.raises(Exception) as excinfo:
        reject_raw_path_authority("/tmp/raw")
    assert getattr(excinfo.value, "error_code", "") == "invalid_execution_context"


def test_conflict_and_snapshot_fixture_shapes(fixture_doc: dict) -> None:
    conflict = ConversationConflictPayload.model_validate(fixture_doc["stale_conflict_example"])
    assert conflict.error == "stale_conversation_revision"
    snapshot = ConversationSnapshot.model_validate(fixture_doc["conversation_snapshot_example"])
    assert snapshot.revision == 4
    assert snapshot.retained_message_ids == ("msg_1", "msg_2")


def test_error_factory_matches_http_map(fixture_doc: dict) -> None:
    for code, status in fixture_doc["error_http_status"].items():
        err = execution_context_error_from_code(code)
        assert err.error_code == code
        assert err.status_code == status
