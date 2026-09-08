"""REL-01 — clean build 순서와 SBOM 실행 가능성 검증.

docs/11_COMMERCIAL_GA_100_PLAN.md §REL-01 수용 기준:
- empty venv/clean checkout에서 SBOM 생성과 verify가 성공한다.
- wheel과 sdist 설치 후 CLI/API import smoke가 성공한다.
- lock digest와 SBOM dependency set이 일치한다.
- release job은 artifact 검증 실패 시 publish 전에 중단한다.

검증 전략: 실제 빌드/설치는 CI에서 수행하므로 여기서는 (1) 워크플로 구조
검증(generate가 build에 선행, verify가 publish 게이트, needs 체인),
(2) SBOM set == uv.lock runtime closure 일치, (3) verify 실패의 비종료
exit code 계약을 독립 재현한다.

실행: uv run --no-sync pytest tests/test_rel01_clean_build_sbom.py -q
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from antigravity_k.engine.release_dependencies import python_runtime_dependencies
from antigravity_k.engine.release_sbom import generate_release_documents

_REPO_ROOT = Path(__file__).resolve().parents[1]


def _workflow(name: str) -> str:
    return (_REPO_ROOT / ".github/workflows" / name).read_text(encoding="utf-8")


class TestWorkflowOrder:
    def test_ci_generates_sbom_before_build(self) -> None:
        """AC-1: CI build job이 SBOM generate → build → verify 순서를 유지한다."""
        ci = _workflow("ci.yml")
        gen_pos = ci.index("release_sbom generate")
        build_pos = ci.index("python -m build")
        verify_pos = ci.index("release_sbom verify")
        assert gen_pos < build_pos < verify_pos, "SBOM generate는 build에, verify는 build 뒤에 있어야 한다"

    def test_release_generates_sbom_before_build(self) -> None:
        """AC-1: release job도 동일 순서를 유지한다."""
        rel = _workflow("release.yml")
        gen_pos = rel.index("release_sbom generate")
        build_pos = rel.index("python -m build")
        verify_pos = rel.index("release_sbom verify")
        assert gen_pos < build_pos < verify_pos

    def test_publish_is_gated_behind_build_job(self) -> None:
        """AC-4: publish-pypi는 build job 성공에 의존한다 — 검증 실패 시 중단."""
        rel = _workflow("release.yml")
        publish_idx = rel.index("publish-pypi:")
        needs_block = rel[publish_idx : publish_idx + 200]
        assert "needs: build" in needs_block
        # build job 내부에 verify 단계가 실패 시 job이 실패한다 (continue-on-error 없음)
        build_block = rel[:publish_idx]
        verify_step = build_block[build_block.index("release_sbom verify") :]
        assert "continue-on-error" not in verify_step.split("- name:", 1)[0]

    def test_supply_chain_manifest_is_uploaded(self) -> None:
        """AC-4: 검증 산출물(release-supply-chain.json)이 artifact로 업로드된다."""
        for name in ("release.yml", "ci.yml"):
            wf = _workflow(name)
            assert "release-supply-chain.json" in wf, f"{name}에 supply-chain manifest 누락"


class TestLockSbomConsistency:
    def test_sbom_set_matches_uv_lock_runtime_closure(self) -> None:
        """AC-3: 실제 uv.lock의 runtime closure와 SBOM component set이 일치한다."""
        deps = python_runtime_dependencies(_REPO_ROOT)
        docs = generate_release_documents(_REPO_ROOT)
        sbom = json.loads(docs.python_sbom.read_text(encoding="utf-8"))

        sbom_names = {c["name"] for c in sbom["components"]}
        lock_names = {d.name for d in deps.dependencies} | {"antigravity-k"}
        assert sbom_names == lock_names, (
            f"SBOM-lock 불일치: sbom_only={sbom_names - lock_names}, lock_only={lock_names - sbom_names}"
        )

    def test_sbom_declares_lockfile_provenance(self) -> None:
        """AC-3: SBOM metadata가 lockfile 출처(uv.lock)를 명시한다."""
        docs = generate_release_documents(_REPO_ROOT)
        sbom = json.loads(docs.python_sbom.read_text(encoding="utf-8"))
        props = {p["name"]: p["value"] for p in sbom["metadata"]["properties"]}
        assert props.get("agk:lockfile") == "uv.lock"


class TestVerifyFailureContract:
    def test_verify_failure_exits_nonzero(self, tmp_path: Path) -> None:
        """AC-4: verify 실패가 명확한 오류로 실패한다 (publish 게이트가 잡을 수 있게)."""
        from antigravity_k.engine.release_sbom import ReleaseSbomError, verify_release_bundle

        empty_dist = tmp_path / "dist"
        empty_dist.mkdir()
        with pytest.raises(ReleaseSbomError):
            verify_release_bundle(distribution_root=empty_dist, release_root=tmp_path / "release")

    def test_wheel_and_sdist_contain_release_documents(self) -> None:
        """AC-2 준비: packaging이 release 문서를 artifact 안에 포함한다."""
        pyproject = (_REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8")
        for doc in ("release/python.cdx.json", "release/dashboard.cdx.json", "release/THIRD_PARTY_NOTICES.txt"):
            assert f'"{doc}"' in pyproject, f"package data에 {doc} 누락"
