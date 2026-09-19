"""task 15 계약 시험 — 번들 검색 artifact 의 배치·갱신·rollback·오프라인.

여기서 고정하는 문장:

- **어느 bytes 를 실행하는지 모르면 실행하지 않는다**: 명시 → 갱신 저장소 → 설치 패키지 순으로 찾고,
  셋 다 없으면 이유를 남긴다. 명시 경로가 **있는데 없으면** 조용히 다른 것으로 내려가지 않는다.
- **정상 설치에는 경로 입력이 필요 없다**: 설치 패키지가 번들을 들고 있으면 `enabled=true` 만으로 유효하다
  (그게 정상 설치의 모습이고, 경로를 손으로 적게 만드는 설계는 곧 "임의 최신 다운로드"가 된다).
- **검증이 통과한 것만 승격된다**: sha256·호스트 arch·selftest. 잘린 다운로드·다른 아키텍처·신뢰 밖
  매니페스트·실패하는 후보는 모두 거절되고 저장소는 손대지 않은 상태로 남는다.
- **바이트는 제자리에서 바뀌지 않는다**: 버전마다 자기 디렉터리, "현재"는 작은 포인터 파일. 실행 중
  child 가 있으면 교체를 보류한다.
- **갱신 도중 죽어도 이전 버전이 남는다**, 그리고 rollback 이 그 버전으로 되돌린다.
- **오프라인은 정직하다**: 기동·상태 조회는 성공하고, 검색은 NETWORK_UNAVAILABLE(영구)로 실패한다 —
  legacy 로 대체하지 않는다(어차피 네트워크가 필요하므로 "두 번 실패"만 보여준다).
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
from typing import Any

import pytest

from antigravity_k.tools import ssak_bundle_store as store
from antigravity_k.tools.ssak_search_provider import (
    NETWORK_UNAVAILABLE,
    ProviderAttempt,
    SsakSearchSettings,
    classify_error_code,
    network_available,
    search_with_bundled_provider,
)

REAL_BUNDLE = Path(__file__).resolve().parent.parent / "src" / "antigravity_k" / "vendor" / "ssak_search"


@pytest.fixture(autouse=True)
def trusted_staging(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """갱신 소스는 **신뢰 루트 안**에 놓는 것이 계약이다(밖이면 거절되는 것이 정상).

    그래서 시험은 임시 디렉터리를 명시적 신뢰 루트로 선언한다 — 실제 운영에서 그 역할은 설치
    트리·사용자 저장소·운영자가 지정한 스테이징 디렉터리다.
    """
    monkeypatch.setenv("AGK_SEARCH_TRUSTED_ROOTS", str(tmp_path))


def make_bundle(
    root: Path, *, payload: bytes = b"#!/bin/sh\necho ssak-mcp-standalone 2.9.0\n", arch: str = "arm64"
) -> Path:
    """`bin/ssak-mcp` + `release/ssak-search-manifest.json` 배치를 만들고 바이너리 경로를 돌려준다."""
    binary = root / "bin" / "ssak-mcp"
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(payload)
    binary.chmod(0o755)
    manifest = root / "release" / "ssak-search-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "artifact": {
                    "sha256": hashlib.sha256(payload).hexdigest(),
                    "size_bytes": len(payload),
                    "platform": store.host_platform(),
                    "arch": arch,
                    "format": "script",
                },
                "product": {"name": "ssak-mcp-standalone", "version": "2.9.0"},
            }
        ),
        encoding="utf-8",
    )
    return binary


# ── 해석 순서 ────────────────────────────────────────────────────────────────


def test_resolution_prefers_explicit_then_store_then_package(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    packaged = tmp_path / "package"
    make_bundle(packaged)
    monkeypatch.setenv(store.BUNDLE_DIR_ENV, str(packaged))
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))

    from_package = store.resolve_bundle()
    assert from_package.layout is not None and from_package.layout.source == store.SOURCE_PACKAGE

    explicit_dir = tmp_path / "explicit"
    explicit = make_bundle(explicit_dir)
    from_explicit = store.resolve_bundle(str(explicit))
    assert from_explicit.layout is not None and from_explicit.layout.source == store.SOURCE_EXPLICIT


def test_an_explicit_path_that_does_not_exist_is_reported_and_never_silently_replaced(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """명시 경로가 깨졌을 때 **다른 바이트를 대신 실행하지 않는다** — 가장 나쁜 결과를 막는다."""
    make_bundle(tmp_path / "package")
    monkeypatch.setenv(store.BUNDLE_DIR_ENV, str(tmp_path / "package"))
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))

    resolution = store.resolve_bundle(str(tmp_path / "missing" / "ssak-mcp"))

    assert resolution.layout is None
    assert resolution.reason and "does not exist" in resolution.reason


def test_nothing_available_says_where_it_looked(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(store.BUNDLE_DIR_ENV, str(tmp_path / "no-package"))
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "no-store"))

    resolution = store.resolve_bundle()

    assert resolution.layout is None
    assert "installed package" in (resolution.reason or "")
    assert "update store" in (resolution.reason or "")


# ── 정상 설치에는 경로 입력이 필요 없다 ──────────────────────────────────────


def test_a_packaged_bundle_makes_enabled_true_valid_without_an_explicit_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """설치본이 번들을 들고 있으면 `enabled=true` 만으로 유효하다 — 정상 설치의 모습."""
    from antigravity_k.tools.ssak_search_provider import _validate, settings_snapshot

    make_bundle(tmp_path / "package")
    monkeypatch.setenv(store.BUNDLE_DIR_ENV, str(tmp_path / "package"))
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))

    assert _validate({"enabled": True}) is None
    settings = settings_snapshot()
    assert settings.problem is None
    bundle = store.resolve_bundle()
    assert bundle.layout is not None
    assert bundle.layout.source == store.SOURCE_PACKAGE


def test_without_any_bundle_enabled_true_is_still_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """fail-closed 는 그대로다 — 번들이 어디에도 없으면 \"어느 bytes 를 실행할지 모른다\"."""
    from antigravity_k.tools.ssak_search_provider import _validate

    monkeypatch.setenv(store.BUNDLE_DIR_ENV, str(tmp_path / "no-package"))
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "no-store"))

    problem = _validate({"enabled": True})

    assert problem is not None
    assert "artifact_path" in problem


def test_bundled_runtime_config_points_at_the_packaged_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """명시 경로가 없어도 런타임 설정이 **실제 번들**을 가리킨다(그래야 켠 검색이 동작한다)."""
    from antigravity_k.tools.ssak_search_provider import bundled_runtime_config

    binary = make_bundle(tmp_path / "package")
    monkeypatch.setenv(store.BUNDLE_DIR_ENV, str(tmp_path / "package"))
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))

    config = bundled_runtime_config(SsakSearchSettings(enabled=True))

    assert config.artifact_path == str(binary)
    assert config.manifest_path is not None and config.manifest_path.endswith("ssak-search-manifest.json")


# ── 갱신: 거절되는 것들 ─────────────────────────────────────────────────────


def test_stage_refuses_a_truncated_download(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))
    make_bundle(tmp_path / "v1")
    manifest = tmp_path / "v1" / "release" / "ssak-search-manifest.json"
    truncated = tmp_path / "truncated"
    truncated.parent.mkdir(parents=True, exist_ok=True)
    truncated.write_bytes((tmp_path / "v1" / "bin" / "ssak-mcp").read_bytes()[:4])
    truncated.chmod(0o755)

    staged = store.stage_update(truncated, manifest, root=tmp_path / "store")

    assert staged.ok is False and staged.code == store.CODE_SHA_MISMATCH
    assert not (tmp_path / "store" / store.VERSIONS_DIRNAME).exists() or not list(
        (tmp_path / "store" / store.VERSIONS_DIRNAME).iterdir()
    )
    assert store.read_pointer(tmp_path / "store") is None


def test_stage_refuses_a_different_architecture(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))
    binary = make_bundle(tmp_path / "v1")
    manifest = tmp_path / "v1" / "release" / "ssak-search-manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    payload["artifact"]["arch"] = "x64" if store.host_arch() != "x64" else "arm64"
    manifest.write_text(json.dumps(payload), encoding="utf-8")

    staged = store.stage_update(binary, manifest, root=tmp_path / "store")

    assert staged.ok is False and staged.code == store.CODE_WRONG_ARCH
    assert store.read_pointer(tmp_path / "store") is None


def test_stage_refuses_a_manifest_outside_the_trusted_roots(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """신뢰 루트 밖 + 핀과도 다른 sha → 거절. 임의 다운로드를 실행 파일의 권위로 받지 않는다."""
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))
    # 신뢰 루트는 **다른** 디렉터리다 — 매니페스트가 그 밖에 있으면 거절된다.
    monkeypatch.setenv("AGK_SEARCH_TRUSTED_ROOTS", str(tmp_path / "trusted"))
    binary = make_bundle(tmp_path / "inside")
    outside = tmp_path.parent / f"ssak15-untrusted-{os.getpid()}.json"
    outside.write_text((tmp_path / "inside" / "release" / "ssak-search-manifest.json").read_text(encoding="utf-8"))

    staged = store.stage_update(binary, outside, root=tmp_path / "store")

    assert staged.ok is False and staged.code == store.CODE_UNTRUSTED
    outside.unlink(missing_ok=True)


def test_a_manifest_that_matches_the_pin_is_accepted_from_anywhere(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """핀과 같은 sha 를 기술한 매니페스트는 **어디서 가져와도** 같은 바이트다 — 복구·재설치 경로."""
    if not (REAL_BUNDLE / "PINNED.json").is_file():
        pytest.skip("no vendored pin in this checkout")
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))
    monkeypatch.delenv("AGK_SEARCH_TRUSTED_ROOTS", raising=False)
    # 이 시험은 **설치본의 핀**을 재므로 패키지 디렉터리를 실제 vendored 트리로 되돌린다.
    monkeypatch.setenv(store.BUNDLE_DIR_ENV, str(REAL_BUNDLE))
    pin = store.pin_sha256()
    assert pin is not None
    # 실물 64MB 바이트가 필요하므로 vendored 트리가 있을 때만 돈다(클린룸은 verify 스크립트가 맡는다).
    copied = tmp_path / "copy"
    binary = make_bundle(copied, payload=(REAL_BUNDLE / "bin" / "ssak-mcp").read_bytes())
    manifest = copied / "release" / "ssak-search-manifest.json"
    outside = tmp_path / "outside-manifest.json"
    outside.write_text(manifest.read_text(encoding="utf-8"))

    verdict = store.verify_bundled_artifact(binary, manifest)
    assert verdict.ok and verdict.sha256 == pin
    # 신뢰 판정만 따로 본다(스테이징은 64MB 복사 + 실행이라 여기서는 과하다).
    assert store._is_trusted_manifest(outside, sha256=pin) is True


def test_stage_refuses_a_candidate_that_fails_its_selftest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """sha 가 맞아도 **실행해 보면 실패하는** 후보는 승격되지 않는다."""
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))
    binary = make_bundle(tmp_path / "v1", payload=b"#!/bin/sh\nexit 7\n")
    manifest = tmp_path / "v1" / "release" / "ssak-search-manifest.json"

    staged = store.stage_update(binary, manifest, root=tmp_path / "store")

    assert staged.ok is False and staged.code == store.CODE_SELFTEST_FAILED


def test_stage_refuses_an_update_without_a_manifest(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))
    binary = make_bundle(tmp_path / "v1")

    staged = store.stage_update(binary, None, root=tmp_path / "store")

    assert staged.ok is False and staged.code == store.CODE_MISSING


# ── 갱신·rollback·보류 ──────────────────────────────────────────────────────


def _install(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path, store.StageResult]:
    """v1 을 저장소에 설치하고 (store_root, v1_dir, stage) 를 돌려준다."""
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))
    binary = make_bundle(tmp_path / "v1")
    manifest = tmp_path / "v1" / "release" / "ssak-search-manifest.json"
    staged = store.stage_update(binary, manifest, root=tmp_path / "store", expected_version="v1")
    committed = store.commit_update(staged, root=tmp_path / "store")
    assert staged.ok and committed.committed, staged.detail
    return tmp_path / "store", tmp_path / "store" / store.VERSIONS_DIRNAME / "v1", staged


def test_commit_swaps_the_pointer_and_keeps_the_previous_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, v1_dir, _staged = _install(tmp_path, monkeypatch)
    before = (v1_dir / "bin" / "ssak-mcp").stat().st_mtime_ns
    v2 = make_bundle(tmp_path / "v2", payload=b"#!/bin/sh\necho ssak-mcp-standalone 2.9.1\n")
    v2_manifest = tmp_path / "v2" / "release" / "ssak-search-manifest.json"
    staged_v2 = store.stage_update(v2, v2_manifest, root=root, expected_version="v2")

    committed = store.commit_update(staged_v2, root=root)

    assert committed.committed and committed.version == "v2" and committed.previous_version == "v1"
    assert (root / store.VERSIONS_DIRNAME / "v1").is_dir(), "이전 버전 디렉터리가 사라졌다"
    # 바이트는 제자리에서 바뀌지 않는다 — v1 의 파일은 그대로다.
    assert (v1_dir / "bin" / "ssak-mcp").stat().st_mtime_ns == before
    assert store.store_bundle(root).version == "v2"  # type: ignore[union-attr]


def test_a_crash_between_stage_and_commit_keeps_the_previous_version(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """스테이징과 커밋 사이에서 죽으면 **이전 버전이 계속 현재 버전**이다."""
    root, _v1_dir, _staged = _install(tmp_path, monkeypatch)
    v2 = make_bundle(tmp_path / "v2", payload=b"#!/bin/sh\necho ssak-mcp-standalone 2.9.1\n")
    v2_manifest = tmp_path / "v2" / "release" / "ssak-search-manifest.json"

    store.stage_update(v2, v2_manifest, root=root, expected_version="v2")  # 승격하지 않는다 = 크래시

    pointer = store.read_pointer(root)
    assert pointer is not None and pointer["version"] == "v1"
    assert store.current_version_dir(root) == root / store.VERSIONS_DIRNAME / "v1"


def test_rollback_restores_the_previous_version_and_reports_when_it_cannot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, _v1_dir, _staged = _install(tmp_path, monkeypatch)

    nothing_to_undo = store.rollback(root=root)
    assert nothing_to_undo.ok is False and nothing_to_undo.missing is True

    v2 = make_bundle(tmp_path / "v2", payload=b"#!/bin/sh\necho ssak-mcp-standalone 2.9.1\n")
    staged_v2 = store.stage_update(
        v2, tmp_path / "v2" / "release" / "ssak-search-manifest.json", root=root, expected_version="v2"
    )
    store.commit_update(staged_v2, root=root)

    rolled = store.rollback(root=root)

    assert rolled.ok and rolled.version == "v1" and rolled.restored_from == "v2"
    assert store.store_bundle(root).version == "v1"  # type: ignore[union-attr]


def test_commit_is_deferred_while_a_search_child_is_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """실행 중 child 가 있으면 승격을 **보류**한다(다음 안전 시점에 다시 부른다).

    런타임의 시야를 주입한다 — 실제 child 를 띄운 판정은 `scripts/verify_ssak_bundle.py` 의
    `update_defers_while_a_child_is_running` 케이스가 실물로 재고, 여기서는 부기 규칙만 고정한다.
    """
    root, _v1_dir, _staged = _install(tmp_path, monkeypatch)
    v2 = make_bundle(tmp_path / "v2", payload=b"#!/bin/sh\necho ssak-mcp-standalone 2.9.1\n")
    staged_v2 = store.stage_update(
        v2, tmp_path / "v2" / "release" / "ssak-search-manifest.json", root=root, expected_version="v2"
    )
    monkeypatch.setattr(store, "_child_running", lambda: [4242])

    deferred = store.commit_update(staged_v2, root=root)

    assert deferred.deferred is True and deferred.committed is False
    assert deferred.running_children == [4242]
    assert store.store_bundle(root).version == "v1"  # type: ignore[union-attr]

    # 안전 시점(기본값 allow_live_swap=False 로도 child 가 없어진 뒤)에는 승격된다.
    monkeypatch.setattr(store, "_child_running", list)
    assert store.commit_update(staged_v2, root=root).committed is True


def test_rollback_is_also_deferred_while_a_child_is_running(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root, _v1_dir, _staged = _install(tmp_path, monkeypatch)
    v2 = make_bundle(tmp_path / "v2", payload=b"#!/bin/sh\necho ssak-mcp-standalone 2.9.1\n")
    staged_v2 = store.stage_update(
        v2, tmp_path / "v2" / "release" / "ssak-search-manifest.json", root=root, expected_version="v2"
    )
    store.commit_update(staged_v2, root=root)
    monkeypatch.setattr(store, "_child_running", lambda: [99])

    deferred = store.rollback(root=root)

    assert deferred.ok is False and "waits for the next safe point" in deferred.detail
    assert store.store_bundle(root).version == "v2"  # type: ignore[union-attr]


def test_staging_the_same_version_twice_does_not_rewrite_the_bytes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root, v1_dir, _staged = _install(tmp_path, monkeypatch)
    binary = v1_dir / "bin" / "ssak-mcp"
    before = binary.stat().st_mtime_ns

    staged_again = store.stage_update(
        tmp_path / "v1" / "bin" / "ssak-mcp",
        tmp_path / "v1" / "release" / "ssak-search-manifest.json",
        root=root,
        expected_version="v1",
    )

    assert staged_again.ok and "already staged" in staged_again.detail
    assert binary.stat().st_mtime_ns == before


# ── 오프라인 정직성 ─────────────────────────────────────────────────────────


def test_offline_switch_makes_the_probe_report_no_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGK_SEARCH_OFFLINE", "1")
    assert network_available(force_probe=True) is False
    monkeypatch.setenv("AGK_SEARCH_OFFLINE", "0")
    assert network_available(force_probe=True) is True


def test_a_transient_failure_while_offline_is_reported_as_network_unavailable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """오프라인에서 transport 실패를 \"일시 장애\"라고 말하면 사용자는 번들이 고장났다고 읽는다."""
    monkeypatch.setenv("AGK_SEARCH_OFFLINE", "1")
    monkeypatch.setenv(store.BUNDLE_DIR_ENV, str(tmp_path / "package"))
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))
    binary = make_bundle(tmp_path / "package")

    class _TransportLost:
        def call_tool(self, name: str, arguments: Any, **_: Any) -> Any:
            class _Outcome(str):
                is_error = True
                error_code = "TRANSPORT_LOST"

            return _Outcome("search child failed: connection refused")

    attempt = search_with_bundled_provider(
        "질의",
        settings=SsakSearchSettings(enabled=True, artifact_path=str(binary), extra_trusted_roots=(str(tmp_path),)),
        runtime=_TransportLost(),
    )

    assert isinstance(attempt, ProviderAttempt)
    assert attempt.ok is False
    assert attempt.error_code == NETWORK_UNAVAILABLE
    assert classify_error_code(NETWORK_UNAVAILABLE) == "permanent"
    assert attempt.transient is False, "오프라인 실패는 legacy 로 대체되지 않는다"
    assert attempt.evidence is not None and attempt.evidence.error_code == NETWORK_UNAVAILABLE
    assert "오프라인" in (attempt.evidence.message if attempt.evidence else "")
    # 사용자가 보는 문장에도 설명이 실린다 — 오류 코드나 raw `ENOTFOUND` 만 보여주면 알 수 없다.
    assert "네트워크에 연결하지 못했습니다" in attempt.message


def test_a_packaged_bundle_passes_the_trust_gate_without_an_explicit_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """정상 설치(경로를 손으로 적지 않은 상태)의 검색이 `UNTRUSTED_ARTIFACT_PATH` 로 거짓 거절되면 안 된다.

    이 결함은 오프라인 실측이 잡았다(E/task-15/artifacts/offline-api.txt): 신뢰 판정이
    `settings.artifact_path`(**None**)만 보고 판단해, 설치 패키지가 번들을 들고 있어도 모든 검색이
    거절됐다. 그래서 판정 대상은 **실제로 실행할 바이트**여야 한다.
    """
    monkeypatch.setenv(store.BUNDLE_DIR_ENV, str(tmp_path / "package"))
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))
    make_bundle(tmp_path / "package")

    class _ReachedTheChild:
        """여기까지 왔으면 신뢰 게이트를 통과한 것이다(그 사실만 재면 되므로 실패를 돌려준다)."""

        def call_tool(self, name: str, arguments: Any, **_: Any) -> Any:
            class _Outcome(str):
                is_error = True
                error_code = "TRANSPORT_LOST"

            return _Outcome("reached the child")

    # 임시 디렉터리가 이 시험에서 "설치 트리" 역할을 한다(실제 설치에서 그 역할은 패키지 트리가
    # 기본 신뢰 루트로 맡는다 — 그 경로는 `scripts/verify_ssak_bundle.py --clean-room` 이 실물로 잰다).
    attempt = search_with_bundled_provider(
        "질의",
        settings=SsakSearchSettings(enabled=True, extra_trusted_roots=(str(tmp_path),)),  # artifact_path 없음
        runtime=_ReachedTheChild(),
    )

    assert attempt.error_code != "UNTRUSTED_ARTIFACT_PATH", attempt.message
    assert attempt.error_code == "TRANSPORT_LOST"


def test_without_the_offline_switch_a_transport_failure_stays_transient(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """스위치가 없을 때(네트워크가 있는 호스트)는 기존 분류 그대로다 — 거짓 \"네트워크 없음\" 금지."""
    monkeypatch.setenv("AGK_SEARCH_OFFLINE", "0")
    monkeypatch.setenv(store.BUNDLE_DIR_ENV, str(tmp_path / "package"))
    monkeypatch.setenv(store.STORE_DIR_ENV, str(tmp_path / "store"))
    binary = make_bundle(tmp_path / "package")

    class _TransportLost:
        def call_tool(self, name: str, arguments: Any, **_: Any) -> Any:
            class _Outcome(str):
                is_error = True
                error_code = "TRANSPORT_LOST"

            return _Outcome("search child failed: connection refused")

    attempt = search_with_bundled_provider(
        "질의",
        settings=SsakSearchSettings(enabled=True, artifact_path=str(binary), extra_trusted_roots=(str(tmp_path),)),
        runtime=_TransportLost(),
    )

    assert attempt.error_code == "TRANSPORT_LOST" and attempt.transient is True


# ── 핀·패키지 데이터 드리프트 ───────────────────────────────────────────────


def _glob_covers(pattern: str, path: str) -> bool:
    """`vendor/ssak_search/bin/*` 가 `vendor/ssak_search/bin/ssak-mcp` 를 덮는가(작은 패턴 일치기)."""
    prefix = pattern[: pattern.index("*")]
    return path.startswith(prefix) and len(path) > len(prefix)


def test_the_pin_and_package_data_agree() -> None:
    """핀이 기술한 바이트가 실제로 패키지 데이터에 실리는가 — 빠지면 설치본에 번들이 안 실린다."""
    pin_file = REAL_BUNDLE / "PINNED.json"
    if not pin_file.is_file():
        pytest.skip("no vendored pin in this checkout")
    pin = json.loads(pin_file.read_text(encoding="utf-8"))
    assert pin["artifact"]["sha256"] and pin["artifact"]["size_bytes"] > 0
    assert pin["materialize"]["why_not_committed"]

    repo = Path(__file__).resolve().parent.parent
    pyproject = (repo / "pyproject.toml").read_text(encoding="utf-8")
    for entry in pin["package_data"]:
        assert entry in pyproject, f"{entry} is missing from [tool.setuptools.package-data]"
    for required in ("vendor/ssak_search/bin/ssak-mcp", "vendor/ssak_search/release/ssak-search-manifest.json"):
        assert any(_glob_covers(entry, required) for entry in pin["package_data"]), (
            f"no package-data entry ships {required}"
        )
    assert "vendor/ssak_search/bin/" in (repo / ".gitignore").read_text(encoding="utf-8"), (
        "the 64MB artifact must stay out of git while the pin is tracked"
    )


def test_vendored_bytes_match_the_pin_when_present() -> None:
    binary = REAL_BUNDLE / "bin" / "ssak-mcp"
    if not binary.is_file():
        pytest.skip("the artifact has not been materialized in this checkout")
    pin = json.loads((REAL_BUNDLE / "PINNED.json").read_text(encoding="utf-8"))
    assert store.verify_bundled_artifact(binary, REAL_BUNDLE / "release" / "ssak-search-manifest.json").ok
    assert binary.stat().st_size == pin["artifact"]["size_bytes"]


# ── 검증 스크립트의 케이스가 살아 있는가 ─────────────────────────────────────


def test_the_node_free_case_is_wired_and_guarded_against_a_vacuous_pass() -> None:
    """ "Node/Bun 없이 동작한다"는 케이스가 **사라지거나 무의미하게 초록이 되지 않게** 소스로 잡는다.

    왜 소스 게이트인가: 이 케이스는 휠 빌드·venv 생성 때문에 QA 러너에서 매번 돌리기엔 느리다. 그렇다고
    게이트를 안 걸면 다음 사람이 `--clean-room` 에서 이 한 줄을 지워도 아무도 모른다(장식이 된다).
    """
    script = (Path(__file__).resolve().parent.parent / "scripts" / "verify_ssak_bundle.py").read_text(encoding="utf-8")
    assert 'runner.case(\n            "clean_room_runs_without_node_or_bun"' in script, "케이스가 사라졌다"
    assert 'bare = {"PATH": "/usr/bin:/bin"}' in script, "런타임 없는 PATH 로 다시 실행하지 않는다"
    # 이빨: 가드 문장 자체. 이게 없으면 "런타임이 있어서 통과"와 "필요 없어서 통과"가 구별되지 않는다.
    assert "if shutil.which(name)" in script and "assert not leaked" in script, "전제(런타임 부재)를 검사하지 않는다"
    assert "env=bare" in script, "만든 PATH 가 실제로 쓰이지 않는다(변수를 만들고 버리면 무의미하다)"
