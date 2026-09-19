"""REL-02 계약 고정 — frontend lock/output와 Docker runtime 계약.

GA-100 plan §REL-02:
  - 단일 package manager/lockfile = pnpm + dashboard/pnpm-lock.yaml.
  - Vite outDir === wheel package-data === Docker COPY 경로 (src/antigravity_k/dashboard_dist).
  - Dockerfile dashboard 빌드는 frozen install을 사용한다.
  - 런타임 이미지에 git이 있고 entrypoint가 fail-fast 검증을 수행한다.
  - 비루트 사용자(agk) + 데이터 디렉터리 소유권.

이 테스트들은 정적 계약을 고정한다 — Docker 데몬이 필요한 통합 검증은
문서의 실측 절차(빌드 + container smoke)로 수행한다.
"""

from __future__ import annotations

import re
import tomllib
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DASHBOARD = PROJECT_ROOT / "dashboard"
DOCKERFILE = PROJECT_ROOT / "Dockerfile"
ENTRYPOINT = PROJECT_ROOT / "docker-entrypoint.sh"


def _dockerfile() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


# ── 단일 package manager/lockfile ───────────────────────────────


def test_package_manager_is_pnpm_with_pinned_version() -> None:
    package_json = (DASHBOARD / "package.json").read_text(encoding="utf-8")
    match = re.search(r'"packageManager":\s*"pnpm@(\d+\.\d+\.\d+)"', package_json)
    assert match, "package.json에 packageManager pnpm 고정이 필요하다"
    assert match.group(1) == "11.3.0"


def test_pnpm_lockfile_is_the_single_lockfile() -> None:
    assert (DASHBOARD / "pnpm-lock.yaml").is_file()
    npm_lock = DASHBOARD / "package-lock.json"
    if npm_lock.exists():
        # npm lockfile이 남아 있다면 CI·Docker·문서 어디서도 사용하지 않아야 한다
        dockerfile = _dockerfile()
        assert "npm ci" not in dockerfile
        for workflow in (PROJECT_ROOT / ".github" / "workflows").glob("*.yml"):
            text = workflow.read_text(encoding="utf-8")
            if "dashboard" in text:
                assert "npm ci --prefix dashboard" not in text
                assert "npm --prefix dashboard ci" not in text


def test_lockfile_specifiers_match_package_json() -> None:
    """remark-breaks 유령 의존성 사건 재발 방지 — lockfile에 모든 specifiers가 기록된다."""
    package_json = (DASHBOARD / "package.json").read_text(encoding="utf-8")
    data = __import__("json").loads(package_json)
    lock = (DASHBOARD / "pnpm-lock.yaml").read_text(encoding="utf-8")
    deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
    for name in deps:
        assert f"'{name}':" in lock or f'"{name}":' in lock or f"{name}:" in lock, (
            f"{name}이 pnpm-lock.yaml에 없다 — pnpm install 후 커밋할 것"
        )


# ── output path 단일화 ──────────────────────────────────────────


def test_vite_outdir_is_package_data_dir() -> None:
    vite = (DASHBOARD / "vite.config.ts").read_text(encoding="utf-8")
    assert "'../src/antigravity_k/dashboard_dist'" in vite or '"../src/antigravity_k/dashboard_dist"' in vite


def test_wheel_package_data_includes_dashboard_dist() -> None:
    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_data = pyproject["tool"]["setuptools"]["package-data"]["antigravity_k"]
    assert "dashboard_dist/*" in package_data
    assert "dashboard_dist/assets/*" in package_data


def test_docker_copies_vite_outdir_not_dashboard_dist_dir() -> None:
    dockerfile = _dockerfile()
    # Vite outDir는 dashboard/../src/antigravity_k/dashboard_dist 이다 — /app/dashboard/dist가 아니다.
    assert "/app/dashboard/dist" not in dockerfile, "구버전 경로 — Vite outDir와 불일치"
    assert "/app/src/antigravity_k/dashboard_dist/" in dockerfile


# ── frozen install 계약 ─────────────────────────────────────────


def test_dockerfile_dashboard_build_uses_pnpm_frozen_install() -> None:
    dockerfile = _dockerfile()
    assert "pnpm install --frozen-lockfile" in dockerfile
    assert "npm ci" not in dockerfile
    # pnpm 설정(pnpm-workspace.yaml)이 lockfile 설치 레이어에 함께 COPY되어야 한다
    assert "dashboard/pnpm-workspace.yaml" in dockerfile


def test_ci_dashboard_install_is_frozen() -> None:
    ci = (PROJECT_ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
    assert "pnpm --dir dashboard install --frozen-lockfile" in ci


# ── container runtime 계약 ──────────────────────────────────────


def test_runtime_image_ships_git_for_vault() -> None:
    dockerfile = _dockerfile()
    base_stage = dockerfile.split("AS builder")[0]
    assert "git" in base_stage, "런타임 base에 git이 필요하다 (Vault create/commit/read)"


def test_entrypoint_fail_fast_without_git() -> None:
    entry = ENTRYPOINT.read_text(encoding="utf-8")
    assert "command -v git" in entry
    assert "exit 1" in entry


def test_entrypoint_checks_vault_writability() -> None:
    entry = ENTRYPOINT.read_text(encoding="utf-8")
    assert "vault_data" in entry


def test_non_root_user_and_owned_data_dirs() -> None:
    dockerfile = _dockerfile()
    assert "USER agk" in dockerfile
    assert "chown -R agk:agk /app" in dockerfile
    assert "vault_data" in dockerfile


# ── 실측 아티팩트 참조 ──────────────────────────────────────────


@pytest.mark.skipif(
    not (PROJECT_ROOT / ".omo" / "evidence" / "commercial-ga-100" / "REL-02").is_dir(),
    reason="증거 팩은 병합 시점에 추가된다",
)
def test_evidence_pack_documents_live_verification() -> None:
    metadata = (PROJECT_ROOT / ".omo" / "evidence" / "commercial-ga-100" / "REL-02" / "metadata.json").read_text(
        encoding="utf-8"
    )
    for token in ("docker build", "health 200", "vault smoke"):
        assert token in metadata
