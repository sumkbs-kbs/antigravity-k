"""Vault 경로·복원·내보내기 보안 계약 고정 (Phase 58).

================================================================
배경: Phase 56 경로 계약과 동일하게, VaultEngine / vault_privacy /
vault_api 의 보안 경계를 모듈 레벨에서 고정한다. 기존 test_vault.py
의 traversal 테스트는 동작을 검증하지만, 복원 안전 경로·export 기본
redact·privacy path 게이트·API ValueError 매핑까지 한 파일에 모아
재작성이 경계를 조용히 바꾸지 못하게 한다.

잠근 계약:

A. ``VaultEngine._safe_resolve``
   1. 절대 경로 거부
   2. ``..`` 이탈 거부
   3. 심링크가 vault 밖으로 나가면 거부
   4. vault 내부 상대 경로는 resolve 후 허용

B. ``_is_safe_restore_target`` — 파괴적 reset/clean 가드
   5. ``/``, ``$HOME``, ``$HOME/Desktop`` 거부
   6. ``$HOME`` 직계 자식 거부
   7. 더 깊은 프로젝트 경로는 허용

C. ``export_notes``
   8. ``redact`` 기본값 True
   9. redact=True 이면 본문/메타의 시크릿 패턴이 마스킹됨
  10. include_assets=False(기본) 이면 content 키 없음

D. ``resolve_vault_privacy_paths``
  11. ``.md`` 만 허용 / ``.git``·``.chroma`` 세그먼트 거부
  12. resolve_path(ValueError) → INVALID_PATH
  13. apply_vault_privacy_mutation 은 unsafe vault 에서 UNSAFE_VAULT

E. API 교차
  14. vault config 변경은 ``resolve_allowed_path`` 를 통과해야 함
  15. absolute path 가 engine ValueError 를 내면 API는 400 (500 금지)
"""

from __future__ import annotations

import inspect
import os
from pathlib import Path

import pytest

from antigravity_k.api.path_security import PathSecurityError
from antigravity_k.api.routes import vault_api
from antigravity_k.engine.vault import VaultEngine
from antigravity_k.engine.vault_privacy import (
    apply_vault_privacy_mutation,
    resolve_vault_privacy_paths,
)
from antigravity_k.engine.vault_privacy_contracts import (
    VaultPrivacyAction,
    VaultPrivacyError,
    VaultPrivacyFailure,
    VaultPrivacyMutation,
)

# ── A. _safe_resolve ────────────────────────────────────────────


def test_safe_resolve_rejects_absolute_and_traversal(tmp_path: Path) -> None:
    engine = VaultEngine(str(tmp_path / "vault"), sync_rag=False)

    with pytest.raises(ValueError):
        _ = engine._safe_resolve("/tmp/escape.md")  # noqa: SLF001
    with pytest.raises(ValueError):
        _ = engine._safe_resolve("../../etc/passwd.md")  # noqa: SLF001


def test_safe_resolve_rejects_symlink_escape(tmp_path: Path) -> None:
    vault = tmp_path / "vault"
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret.md").write_text("leak", encoding="utf-8")
    engine = VaultEngine(str(vault), sync_rag=False)
    (engine.vault_path / "link").symlink_to(outside, target_is_directory=True)

    with pytest.raises(ValueError):
        _ = engine._safe_resolve("link/secret.md")  # noqa: SLF001


def test_safe_resolve_allows_internal_relative(tmp_path: Path) -> None:
    engine = VaultEngine(str(tmp_path / "vault"), sync_rag=False)
    (engine.vault_path / "notes").mkdir()
    resolved = engine._safe_resolve("notes/a.md")  # noqa: SLF001
    assert resolved == (engine.vault_path / "notes" / "a.md").resolve()
    assert resolved.is_relative_to(engine.vault_path)


# ── B. restore safety ───────────────────────────────────────────


def test_safe_restore_target_blocks_home_desktop_and_home_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    # expanduser("~") 가 HOME 을 쓰도록
    monkeypatch.setattr(os.path, "expanduser", lambda p: str(home) if p == "~" else p)

    engine = VaultEngine(str(tmp_path / "project" / "vault"), sync_rag=False)

    # 정상 깊은 경로는 허용
    assert engine._is_safe_restore_target() is True  # noqa: SLF001

    for dangerous in (Path("/"), home, home / "Desktop", home / "Documents"):
        engine.vault_path = dangerous
        assert engine._is_safe_restore_target() is False, dangerous  # noqa: SLF001


# ── C. export_notes ─────────────────────────────────────────────


def test_export_notes_defaults_to_redact_without_content(tmp_path: Path) -> None:
    sig = inspect.signature(VaultEngine.export_notes)
    assert sig.parameters["redact"].default is True
    assert sig.parameters["include_assets"].default is False

    engine = VaultEngine(str(tmp_path / "vault"), sync_rag=False)
    secret = "NVIDIA_API_KEY=nvabc1234567890secret"
    engine.write_note("private.md", {"title": "t", "token": secret}, f"body {secret}")

    records = engine.export_notes()
    assert len(records) == 1
    assert "content" not in records[0]
    blob = str(records[0]["metadata"])
    assert "nvabc1234567890secret" not in blob


def test_export_notes_redacts_content_when_assets_included(tmp_path: Path) -> None:
    engine = VaultEngine(str(tmp_path / "vault"), sync_rag=False)
    secret = "Bearer eyJhbGciOiJIUzI1NiJ9.aaa.bbb"
    engine.write_note("x.md", {"title": "x"}, secret)

    records = engine.export_notes(include_assets=True, redact=True)
    assert "eyJhbGciOiJIUzI1NiJ9" not in records[0]["content"]
    assert "<REDACTED>" in records[0]["content"]


# ── D. privacy path gate ────────────────────────────────────────


def test_privacy_paths_reject_non_md_and_vcs_segments(tmp_path: Path) -> None:
    engine = VaultEngine(str(tmp_path / "vault"), sync_rag=False)

    with pytest.raises(VaultPrivacyError) as err:
        _ = resolve_vault_privacy_paths(("note.txt",), engine._safe_resolve, require_files=False)  # noqa: SLF001
    assert err.value.failure is VaultPrivacyFailure.INVALID_PATH

    with pytest.raises(VaultPrivacyError) as err2:
        _ = resolve_vault_privacy_paths((".git/config.md",), engine._safe_resolve, require_files=False)  # noqa: SLF001
    assert err2.value.failure is VaultPrivacyFailure.INVALID_PATH


def test_privacy_paths_map_resolver_escape_to_invalid(tmp_path: Path) -> None:
    engine = VaultEngine(str(tmp_path / "vault"), sync_rag=False)
    with pytest.raises(VaultPrivacyError) as err:
        _ = resolve_vault_privacy_paths(("../escape.md",), engine._safe_resolve, require_files=False)  # noqa: SLF001
    assert err.value.failure is VaultPrivacyFailure.INVALID_PATH


def test_privacy_mutation_refuses_unsafe_vault(tmp_path: Path) -> None:
    engine = VaultEngine(str(tmp_path / "vault"), sync_rag=False)
    engine.write_note("a.md", {"title": "a"}, "secret-value")

    with pytest.raises(VaultPrivacyError) as err:
        _ = apply_vault_privacy_mutation(
            vault_path=engine.vault_path,
            acquire_lock=engine._acquire_vault_lock,  # noqa: SLF001
            resolve_path=engine._safe_resolve,  # noqa: SLF001
            mutation=VaultPrivacyMutation(
                action=VaultPrivacyAction.REDACT,
                paths=("a.md",),
                values=("secret-value",),
            ),
            sync_derivatives=lambda *_a, **_k: None,
            is_safe_restore_target=lambda: False,
        )
    assert err.value.failure is VaultPrivacyFailure.UNSAFE_VAULT


# ── E. API 교차 ─────────────────────────────────────────────────


def test_set_vault_config_requires_allowed_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """config 엔드포인트가 resolve_allowed_path 를 우회하면 안 된다."""
    from fastapi import FastAPI
    from fastapi.testclient import TestClient

    app = FastAPI()
    app.include_router(vault_api.router)
    outside = tmp_path / "outside"
    outside.mkdir()

    def deny(_path: str) -> Path:
        raise PathSecurityError("blocked")

    monkeypatch.setattr(vault_api, "resolve_allowed_path", deny)
    client = TestClient(app)
    response = client.post("/api/vault/config", json={"vault_path": str(outside)})
    assert response.status_code == 403


def test_vault_api_maps_engine_path_errors_to_400(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """엔진 ValueError(절대경로/이탈)는 500이 아니라 400이어야 한다."""
    from fastapi.testclient import TestClient

    from antigravity_k.api.dependencies import get_vault_engine
    from antigravity_k.api.server import app
    from antigravity_k.config import config as app_config

    engine = VaultEngine(str(tmp_path / "vault"), sync_rag=False)
    monkeypatch.setattr(vault_api, "_require_allowed", lambda *_a, **_k: None)
    app.dependency_overrides[get_vault_engine] = lambda: engine
    try:
        client = TestClient(app, raise_server_exceptions=False)
        client.headers.update({"X-Access-Pin": app_config.security.access_pin})
        read = client.get("/api/vault/read", params={"path": "/tmp/abs.md"})
        write = client.post("/api/vault/write", json={"path": "/tmp/abs.md", "content": "x"})
    finally:
        _ = app.dependency_overrides.pop(get_vault_engine, None)

    assert read.status_code == 400, read.text
    assert write.status_code == 400, write.text
