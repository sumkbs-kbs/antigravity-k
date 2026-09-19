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
import re
import shutil
from pathlib import Path

import pytest

from antigravity_k.engine.release_dependencies import python_runtime_dependencies
from antigravity_k.engine.release_sbom import generate_release_documents

_REPO_ROOT = Path(__file__).resolve().parents[1]


# 생성기가 읽는 입력은 lockfile 두 개와 provenance 정책 하나뿐이다.
_GENERATOR_INPUTS = ("uv.lock", "dashboard/package-lock.json", "THIRD_PARTY_PROVENANCE.toml")


def _dashboard_block(notices: str) -> str:
    """고지문에서 대시보드 절만 떼어낸다(파이썬 절은 환경 의존이라 비교 대상이 아니다)."""
    marker = "Dashboard dependencies"
    return notices[notices.index(marker) :] if marker in notices else ""


def _first_differing_lines(produced: bytes, committed: bytes) -> tuple[str, str]:
    """처음 갈리는 줄을 찾는다 — 어긋났을 때 어느 패키지인지 바로 보이게 한다."""
    left = produced.decode("utf-8", "replace").splitlines()
    right = committed.decode("utf-8", "replace").splitlines()
    for index, line in enumerate(left):
        counterpart = right[index] if index < len(right) else "<missing>"
        if line != counterpart:
            return line, counterpart
    return f"<{len(left)} lines>", f"<{len(right)} lines>"


def _isolated_project(tmp_path: Path) -> Path:
    """생성기 입력만 복사한 임시 프로젝트 루트.

    `generate_release_documents` 는 문서를 **쓰는** 함수다. 저장소 루트로 부르면
    추적 중인 `src/antigravity_k/release/*` 를 검증 실행이 그대로 덮어써서
    (1) 테스트 후 작업 트리가 더러워지고, (2) 낡은 SBOM이 조용히 재생성되며,
    (3) 같은 코드 상태를 지문으로 고정할 수 없게 된다. 실제 생성물은 여기서만
    만들고, 저장소 사본과의 일치는 별도 검사(아래)가 판정한다.
    """
    root = tmp_path / "project"
    for relative in _GENERATOR_INPUTS:
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(_REPO_ROOT / relative, target)
    return root


def _workflow(name: str) -> str:
    return (_REPO_ROOT / ".github/workflows" / name).read_text(encoding="utf-8")


def _distribution_build_index(text: str) -> int:
    """배포 산출물 빌드 단계의 위치.

    CR-11에서 `python -m build` → `uv build --no-sources`로 바뀌었다(잠금 환경에서
    소스 오버라이드 없이 빌드). 명령 이름에 결합되지 않게 두 형태를 모두 받는다.
    """
    candidates = [text.find(marker) for marker in ("uv build --no-sources", "uv build", "python -m build")]
    found = [index for index in candidates if index >= 0]
    assert found, "배포 산출물 빌드 단계를 찾지 못했습니다"
    return min(found)


class TestWorkflowOrder:
    def test_ci_generates_sbom_before_build(self) -> None:
        """AC-1: CI build job이 SBOM generate → build → verify 순서를 유지한다."""
        ci = _workflow("ci.yml")
        gen_pos = ci.index("release_sbom generate")
        build_pos = _distribution_build_index(ci)
        verify_pos = ci.index("release_sbom verify")
        assert gen_pos < build_pos < verify_pos, "SBOM generate는 build에, verify는 build 뒤에 있어야 한다"

    def test_release_generates_sbom_before_build(self) -> None:
        """AC-1: release job도 동일 순서를 유지한다."""
        rel = _workflow("release.yml")
        gen_pos = rel.index("release_sbom generate")
        build_pos = _distribution_build_index(rel)
        verify_pos = rel.index("release_sbom verify")
        assert gen_pos < build_pos < verify_pos

    def test_publish_is_gated_behind_build_job(self) -> None:
        """AC-4: publish-pypi는 build job 성공에 의존한다 — 검증 실패 시 중단.

        요구는 "build 가 선행 조건이다"이지 `needs: build` 라는 **문자열**이 아니다. CR-14 R-11 이
        `ga-close` 를 같은 자리에 추가했을 때 이 계약이 문자열 결합 때문에 먼저 깨졌다 — 목록을
        **파싱**해 `build` 의 포함 여부를 본다(다른 선행 조건이 늘어도 의도는 그대로 지킨다).
        """
        rel = _workflow("release.yml")
        publish_idx = rel.index("publish-pypi:")
        needs_block = rel[publish_idx : publish_idx + 200]
        needs_line = next(line for line in needs_block.splitlines() if line.strip().startswith("needs:"))
        declared = {item.strip() for item in re.sub(r"[\[\]]", "", needs_line.split(":", 1)[1]).split(",")}
        assert "build" in declared, f"publish-pypi 가 build job 에 의존하지 않는다: {needs_line.strip()!r}"
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
    def test_sbom_set_matches_uv_lock_runtime_closure(self, tmp_path: Path) -> None:
        """AC-3: 실제 uv.lock의 runtime closure와 SBOM component set이 일치한다."""
        project = _isolated_project(tmp_path)
        deps = python_runtime_dependencies(project)
        docs = generate_release_documents(project)
        sbom = json.loads(docs.python_sbom.read_text(encoding="utf-8"))

        sbom_names = {c["name"] for c in sbom["components"]}
        lock_names = {d.name for d in deps.dependencies} | {"antigravity-k"}
        assert sbom_names == lock_names, (
            f"SBOM-lock 불일치: sbom_only={sbom_names - lock_names}, lock_only={lock_names - sbom_names}"
        )

    def test_sbom_declares_lockfile_provenance(self, tmp_path: Path) -> None:
        """AC-3: SBOM metadata가 lockfile 출처(uv.lock)를 명시한다."""
        docs = generate_release_documents(_isolated_project(tmp_path))
        sbom = json.loads(docs.python_sbom.read_text(encoding="utf-8"))
        props = {p["name"]: p["value"] for p in sbom["metadata"]["properties"]}
        assert props.get("agk:lockfile") == "uv.lock"

    def test_committed_dashboard_documents_match_the_generator(self, tmp_path: Path) -> None:
        """저장소 사본의 **대시보드** 산출물이 lock+provenance와 바이트까지 같은지.

        REL-01의 두 테스트가 저장소 루트에 생성하며 이 드리프트를 덮어 왔다. 대시보드
        쪽은 입력이 lockfile과 provenance 정책뿐이라 **환경과 무관하게 결정**된다.
        CR-09이 mermaid 폐쇄를 lock에 넣었는데도 저장소 사본에 반영되지 않던 드리프트
        (수백 줄 차이)를 이 단언이 처음으로 잡는다.
        """
        generated = generate_release_documents(_isolated_project(tmp_path))
        committed_root = _REPO_ROOT / "src" / "antigravity_k" / "release"

        produced_sbom = (generated.release_root / "dashboard.cdx.json").read_bytes()
        committed_sbom = (committed_root / "dashboard.cdx.json").read_bytes()
        assert produced_sbom == committed_sbom, (
            "dashboard.cdx.json이 lockfile과 어긋난다 — "
            "`uv run --isolated --frozen python -m antigravity_k.engine.release_sbom generate "
            "--project-root . --release-root src/antigravity_k/release` 로 저장소 사본을 갱신하라\n"
            f"  생성물: {_first_differing_lines(produced_sbom, committed_sbom)[0]!r}\n"
            f"  저장소: {_first_differing_lines(produced_sbom, committed_sbom)[1]!r}"
        )

        produced_notices = (generated.release_root / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
        committed_notices = (committed_root / "THIRD_PARTY_NOTICES.txt").read_text(encoding="utf-8")
        assert _dashboard_block(produced_notices) == _dashboard_block(committed_notices), (
            "THIRD_PARTY_NOTICES.txt의 대시보드 절이 lockfile과 어긋난다"
        )

    def test_committed_python_sbom_component_set_matches_the_lock(self, tmp_path: Path) -> None:
        """저장소 사본의 파이썬 구성요소 집합이 lock의 runtime closure와 같은지.

        라이선스 **값**은 `importlib.metadata` 로 지금 실행 중인 환경에서 읽히므로
        생성 환경에 따라 달라진다(결함 기록: CR-14 decision D-02 — 저장소 사본은
        release workflow 와 같은 명령으로 만들어야 한다). 그래서 여기서는 환경과
        무관한 구성요소 집합/버전만 고정하고, 라이선스 필드가 통째로 사라지는
        종류의 열화만 막는다.
        """
        project = _isolated_project(tmp_path)
        generated = generate_release_documents(project)
        committed = json.loads(
            (_REPO_ROOT / "src" / "antigravity_k" / "release" / "python.cdx.json").read_text(encoding="utf-8")
        )
        produced = json.loads((generated.release_root / "python.cdx.json").read_text(encoding="utf-8"))
        expected = {
            (dependency.name, dependency.version) for dependency in python_runtime_dependencies(project).dependencies
        }

        produced_components = {(component["name"], component["version"]) for component in produced["components"]}
        committed_components = {(component["name"], component["version"]) for component in committed["components"]}

        assert produced_components == committed_components, (
            f"저장소 사본의 파이썬 SBOM 구성요소가 lock과 어긋난다: {produced_components ^ committed_components}"
        )
        assert expected <= committed_components, sorted(expected - committed_components)
        assert any(component.get("licenses") for component in committed["components"]), (
            "저장소 사본에 라이선스가 하나도 없다 — 열화된 산출물이다"
        )


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
