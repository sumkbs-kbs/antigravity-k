"""allowed_roots / WORKSPACE_ROOT 보안 계약 고정 (Phase 56).

================================================================
배경: Phase 27에서 다른 에이전트의 ``git_api.py`` 재작성이
``_resolve_git_dir``의 기준 우선순위(config 먼저)와 등록 프로젝트 허용
루트 확장을 무너뜨려 12개 git 엔드포인트 테스트가 깨진 적이 있다.
엔드포인트 테스트는 우연히 계약을 걸지만, 이 파일은 **계약 자체**를
모듈 레벨에서 고정해 재작성이 보안 경계를 조용히 바꾸지 못하게 한다.

잠근 계약:

A. ``path_security.allowed_roots()`` — 허용 루트 구성
   1. 첫 번째 루트는 항상 ``config.paths.project_root`` (resolve 후)
   2. 프로젝트 레지스트리 경로가 추가되고, 중복은 제거되며 순서 유지
   3. ``AGK_ALLOWED_ROOTS`` (``os.pathsep`` 구분) 환경변수 루트가 추가됨
   4. 레지스트리 예외 시에도 config 루트로 다운그레이드 없이 동작

B. ``path_security.resolve_allowed_path()`` — 경로 검증
   5. 모든 루트를 검사한다 (첫 루트만 검사해도 통과하는 재작성 금지)
   6. 어떤 루트 밖이면 ``PathSecurityError`` (심링크/``..`` 정규화 후)

C. ``git_api._resolve_git_dir`` — git 작업 디렉터리 경계
   7. 루트 밖 + ``.git`` 없음 → 403 (기존 boundary 테스트 보강)
   8. 루트 밖 + ``.git`` 존재 → 의도적 carve-out으로 허용 (계약 문서화)
   9. 스태일 활성 프로젝트(roots에 없음)는 베이스로 쓰지 않는다
   10. 유효한 활성 프로젝트는 상대 경로 해석 기준을 확장한다

D. ``filesystem.WORKSPACE_ROOT`` — 파일시스템 경계
   11. ``_resolve_workspace_path``가 런타임 WORKSPACE_ROOT 기준으로
       이탈 경로를 403으로 거부한다

E. 교차 일관성
   12. ``allowed_roots()``에 있는 루트의 git 디렉터리는 ``_resolve_git_dir``
       도 받아야 한다 — 두 보안면이 같은 allowlist를 공유한다는 계약.
"""

from __future__ import annotations

import os
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from antigravity_k.api import path_security
from antigravity_k.api.routes import filesystem, git_api
from antigravity_k.config import config

# ────────────────────────────────────────────────────────────────
# 스텁: 전역 ProjectRegistry를 건드리지 않고 호출 지점만 교체한다.
# path_security와 git_api는 호출 시점에 get_project_registry를
# 임포트하므로 소스 모듈 속성만 패치하면 두 경로 모두에 적용된다.
# ────────────────────────────────────────────────────────────────


class _StubRegistry:
    def __init__(
        self,
        projects: list[dict[str, str]] | None = None,
        active_path: str | None = None,
    ) -> None:
        self._projects = projects or []
        self._active_path = active_path

    def list_projects(self) -> list[dict[str, str]]:
        return self._projects

    def get_active_project(self) -> SimpleNamespace:
        if self._active_path is None:
            raise AssertionError("get_active_project should not be called in this test")
        return SimpleNamespace(path=self._active_path)


def _patch_roots(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    *,
    registry: _StubRegistry | None = None,
    extra_roots: str = "",
) -> Path:
    """config 루트/레지스트리/환경변수를 테스트용 allowlist로 고정한다."""
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(config.paths, "project_root", project_root)
    monkeypatch.setattr(
        "antigravity_k.engine.project_registry.get_project_registry",
        lambda: registry or _StubRegistry(),
    )
    if extra_roots:
        monkeypatch.setenv("AGK_ALLOWED_ROOTS", extra_roots)
    else:
        monkeypatch.delenv("AGK_ALLOWED_ROOTS", raising=False)
    return project_root


# ── A. allowed_roots 구성 ────────────────────────────────────────


def test_allowed_roots_starts_with_config_project_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = _patch_roots(monkeypatch, tmp_path)

    roots = path_security.allowed_roots()

    assert roots[0] == project_root.resolve()


def test_allowed_roots_include_registry_projects_without_duplicates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = tmp_path / "project"
    registry = _StubRegistry(
        projects=[
            {"path": str(tmp_path / "alpha")},
            {"path": str(project_root)},  # config 루트와 동일 — 중복 제거 대상
            {"path": str(tmp_path / "beta")},
        ]
    )
    (tmp_path / "alpha").mkdir()
    (tmp_path / "beta").mkdir()

    _ = _patch_roots(monkeypatch, tmp_path, registry=registry)

    roots = path_security.allowed_roots()

    assert roots == (
        project_root.resolve(),
        (tmp_path / "alpha").resolve(),
        (tmp_path / "beta").resolve(),
    )


def test_allowed_roots_append_agk_allowed_roots_env_entries(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    extra_a = tmp_path / "env-a"
    extra_b = tmp_path / "env-b"
    extra_a.mkdir()
    extra_b.mkdir()
    project_root = _patch_roots(
        monkeypatch,
        tmp_path,
        extra_roots=os.pathsep.join([str(extra_a), str(extra_b)]),
    )

    roots = path_security.allowed_roots()

    assert roots == (project_root.resolve(), extra_a.resolve(), extra_b.resolve())


def test_allowed_roots_survive_registry_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = _patch_roots(monkeypatch, tmp_path)

    class _ExplodingRegistry(_StubRegistry):
        def list_projects(self) -> list[dict[str, str]]:
            raise RuntimeError("registry storage corrupted")

    monkeypatch.setattr(
        "antigravity_k.engine.project_registry.get_project_registry",
        lambda: _ExplodingRegistry(),
    )

    roots = path_security.allowed_roots()

    # 레지스트리가 죽어도 config 루트 allowlist는 유지된다 (다운그레이드 없음)
    assert roots == (project_root.resolve(),)


# ── B. resolve_allowed_path 검증 ────────────────────────────────


def test_resolve_allowed_path_checks_every_root_not_only_the_first(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """첫 루트만 검사하는 재작성은 등록 프로젝트 경로를 전부 차단한다."""
    _patch_roots(
        monkeypatch,
        tmp_path,
        registry=_StubRegistry(projects=[{"path": str(tmp_path / "registered")}]),
    )
    registered_file = tmp_path / "registered" / "data.txt"
    registered_file.parent.mkdir()
    registered_file.write_text("x", encoding="utf-8")
    sibling = tmp_path / "sneaky.txt"

    allowed = path_security.resolve_allowed_path(registered_file)
    assert allowed == registered_file.resolve()

    with pytest.raises(path_security.PathSecurityError):
        path_security.resolve_allowed_path(sibling)


def test_resolve_allowed_path_rejects_traversal_even_from_inside(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    project_root = _patch_roots(monkeypatch, tmp_path)

    with pytest.raises(path_security.PathSecurityError):
        path_security.resolve_allowed_path(project_root / "sub" / ".." / ".." / "escape")


# ── C. git_api._resolve_git_dir 경계 ────────────────────────────


def test_git_dir_rejects_root_outside_without_git_dir(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = _patch_roots(monkeypatch, tmp_path)
    plain = tmp_path / "plain-dir"
    plain.mkdir()

    with pytest.raises(HTTPException) as error:
        git_api._resolve_git_dir(str(plain))  # noqa: SLF001 — 계약 자체를 잠그는 테스트

    assert error.value.status_code == 403
    assert project_root.exists()  # (테스트 자체 성립 확인)


def test_git_dir_admits_outside_git_repo_as_intentional_carve_out(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """루트 밖 독립 git 저장소 허용은 문서화된 carve-out이다.

    이 계약을 빼려면 보안 결정이 필요하다 — 조용히 제거되면 안 된다.
    """
    _patch_roots(monkeypatch, tmp_path)
    external_repo = tmp_path / "external-repo"
    (external_repo / ".git").mkdir(parents=True)

    resolved = git_api._resolve_git_dir(str(external_repo))  # noqa: SLF001

    assert resolved == external_repo.resolve()


def test_git_dir_ignores_stale_active_project_outside_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """roots에 없는 활성 프로젝트는 베이스로 쓰지 않는다 (TOCTOU 방어).

    실제 코드에선 allowed_roots()와 get_active_project() 사이에 레지스트리
    파일이 수정되는 창이 존재한다 — 두 읽기가 서로 다른 결과를 주는 상황을
    스텁으로 재현해, 가드가 이 이탈을 막는지 검증한다.
    """
    project_root = tmp_path / "project"
    stale_repo = tmp_path / "stale" / "repo"
    (stale_repo / ".git").mkdir(parents=True)
    # list_projects에는 없고 get_active_project에만 있는 경로 — 읽기 사이 역직렬화
    _ = _patch_roots(
        monkeypatch,
        tmp_path,
        registry=_StubRegistry(
            projects=[],  # allowed_roots(): stale은 roots에 없음
            active_path=str(tmp_path / "stale"),  # get_active_project(): stale 반환
        ),
    )

    # 가드가 있으면: 상대 "repo"는 config 루트 기준으로만 해석 → 존재하지 않음 → 400
    # 가드가 없으면: stale/repo가 베이스 후보가 되어 .git carve-out으로 승인됨
    with pytest.raises(HTTPException) as error:
        git_api._resolve_git_dir("repo")  # noqa: SLF001

    assert error.value.status_code in {400, 403}
    assert project_root.exists()  # (테스트 자체 성립 확인)


def test_git_dir_extends_relative_base_with_valid_active_project(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """등록 프로젝트는 allowed_roots 확장이므로 상대 경로 기준도 된다."""
    work_root = tmp_path / "work"
    (work_root / "repo").mkdir(parents=True)
    _patch_roots(
        monkeypatch,
        tmp_path,
        registry=_StubRegistry(
            projects=[{"path": str(work_root)}],
            active_path=str(work_root),
        ),
        extra_roots=str(work_root),  # 환경변수로 등록 → allowed_roots에 포함
    )

    resolved = git_api._resolve_git_dir("repo")  # noqa: SLF001

    assert resolved == (work_root / "repo").resolve()


# ── D. filesystem WORKSPACE_ROOT 경계 ───────────────────────────


def test_fs_workspace_path_resolver_blocks_escape_at_module_level(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """엔드포인트를 거치지 않는 직접 호출도 같은 경계를 적용해야 한다."""
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    monkeypatch.setattr(filesystem, "WORKSPACE_ROOT", str(workspace))

    with pytest.raises(HTTPException) as error:
        filesystem._resolve_workspace_path("../outside")  # noqa: SLF001

    assert error.value.status_code == 403


def test_fs_workspace_path_resolver_resolves_relative_inside(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    workspace = tmp_path / "workspace"
    (workspace / "sub").mkdir(parents=True)
    monkeypatch.setattr(filesystem, "WORKSPACE_ROOT", str(workspace))

    resolved = filesystem._resolve_workspace_path("sub")  # noqa: SLF001

    assert resolved == str((workspace / "sub").resolve())


# ── E. 교차 일관성 ──────────────────────────────────────────────


def test_git_dir_accepts_every_root_reported_by_allowed_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """allowed_roots()가 허용한다고 보고한 루트는 git 경계도 받아야 한다.

    두 보안면이 서로 다른 allowlist를 갖게 되는 재작성을 잡는다.
    """
    env_root = tmp_path / "env-workspace"
    (env_root / "repo").mkdir(parents=True)
    _patch_roots(monkeypatch, tmp_path, extra_roots=str(env_root))

    roots = path_security.allowed_roots()
    assert env_root.resolve() in roots  # 전제: allowlist에 보고됨

    resolved = git_api._resolve_git_dir(str(env_root / "repo"))  # noqa: SLF001
    assert resolved == (env_root / "repo").resolve()
