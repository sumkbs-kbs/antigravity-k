#!/usr/bin/env python3
"""번들 검색의 설치·오프라인 시작·갱신·rollback 검증 (task 15).

이 스크립트가 답하는 질문들 — 각각이 하나의 케이스다:

  1. **packaged** — 설치 패키지(또는 갱신 저장소)가 들고 있는 번들로 실제 child 를 띄워
     `initialize` + `tools/list` 가 되는가, 그리고 종료 후 child 가 0 인가.
  2. **offline**(`--offline-start`) — 인터넷이 없어도 **기동은 성공**하고, 웹검색은
     `NETWORK_UNAVAILABLE` 로 **정직하게** 실패하는가(일시 장애로 오인되거나 조용히 legacy 로
     대체되지 않는가).
  3. **update/rollback**(`--rollback-test`) — 잘린 다운로드·다른 아키텍처·신뢰 밖 매니페스트가
     모두 거절되고, 갱신 도중 죽어도 **이전 버전이 그대로 현재 버전**이며, rollback 이 되돌리는가.
     실행 중 child 가 있으면 교체를 **보류**하는가.
  4. **clean-room**(`--clean-room`) — 원본 W 체크아웃을 참조하지 않는 임시 환경에서 **S 설치
     패키지만으로**(wheel → 새 venv) `initialize`/`tools/list` 가 되는가.

사용법(repo 루트):
    uv run --frozen python scripts/verify_ssak_bundle.py --offline-start --rollback-test
    uv run --frozen python scripts/verify_ssak_bundle.py --clean-room        # 느리다(휠 빌드·설치)

종료코드 0 = 실행한 케이스 전부 통과. 1 = 하나라도 실패(무엇이 왜 실패했는지 출력).
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO / "src"))

BINARY_NAME = "ssak-mcp"

# `sys.path` 를 먼저 세운 뒤에만 패키지를 import 할 수 있다(주석 위치가 아니라 순서가 이유다).
from antigravity_k.tools.ssak_bundle_store import StageResult  # noqa: E402


@dataclass
class Case:
    """한 케이스의 결과. `ok=False` 면 `detail` 이 사람이 읽을 이유다."""

    name: str
    ok: bool
    detail: str = ""
    facts: dict[str, object] = field(default_factory=dict)


class Runner:
    def __init__(self, *, as_json: bool) -> None:
        self.cases: list[Case] = []
        self.as_json = as_json

    def add(self, case: Case) -> None:
        self.cases.append(case)
        if not self.as_json:
            mark = "PASS" if case.ok else "FAIL"
            print(f"  [{mark}] {case.name}: {case.detail}", flush=True)

    def case(self, name: str, ok: bool, detail: str = "", **facts: object) -> None:
        self.add(Case(name, ok, detail, facts))

    def finish(self) -> int:
        failed = [case for case in self.cases if not case.ok]
        if self.as_json:
            print(json.dumps({"cases": [case.__dict__ for case in self.cases]}, ensure_ascii=False, indent=2))
            return 1 if failed else 0
        print(f"\n{len(self.cases) - len(failed)}/{len(self.cases)} 케이스 통과")
        for case in failed:
            print(f"  FAILED {case.name}: {case.detail}")
        return 1 if failed else 0


# ── 번들 실행(실제 child) ───────────────────────────────────────────────────


def run_bundle_handshake(binary: Path, manifest: Path | None, *, timeout: float = 90.0) -> tuple[bool, str, list[str]]:
    """실제 child 를 띄워 initialize + tools/list 를 한다(런타임 경유 = 배포 경로 그대로)."""
    from antigravity_k.tools.ssak_search_runtime import SearchRuntimeConfig, SsakSearchRuntime

    runtime = SsakSearchRuntime(
        SearchRuntimeConfig(
            artifact_path=str(binary),
            manifest_path=str(manifest) if manifest else None,
            ready_timeout_seconds=timeout,
            call_timeout_seconds=timeout,
        )
    )
    try:
        if not runtime.ensure_ready(timeout=timeout):
            state = runtime.status()
            return False, f"child did not become ready: {state.get('last_error') or state.get('state')}", []
        tools = [str(tool.get("name", "")) for tool in runtime.list_tools(timeout=timeout)]
        if not tools:
            return False, "tools/list returned nothing", []
        return True, f"initialize + tools/list ok ({len(tools)} tools)", tools
    finally:
        teardown = runtime.shutdown(timeout=30.0)
        recorded = teardown.get("child_pids") if teardown else None
        left = [int(pid) for pid in recorded] if isinstance(recorded, (list, tuple)) else []
        if left:  # pragma: no cover — 회수 실패는 그 자체로 결함이다
            print(f"  (경고) shutdown 뒤에도 child 가 남았다: {left}", file=sys.stderr)


# ── 케이스 1: 설치된 번들 ───────────────────────────────────────────────────


def case_packaged(runner: Runner, bundle_dir: Path | None) -> None:
    from antigravity_k.tools.ssak_bundle_store import resolve_bundle
    from antigravity_k.tools.ssak_search_runtime import verify_bundled_artifact

    if bundle_dir is not None:
        os.environ["AGK_SSAK_BUNDLE_DIR"] = str(bundle_dir)
    resolution = resolve_bundle()
    if not resolution.found:
        runner.case("packaged_bundle", False, resolution.reason or "no bundle found")
        return
    layout = resolution.layout
    assert layout is not None
    verdict = verify_bundled_artifact(layout.binary, layout.manifest)
    runner.case(
        "packaged_bundle_integrity",
        verdict.ok,
        verdict.detail,
        sha256=verdict.sha256,
        source=layout.source,
        version=layout.version,
    )
    if not verdict.ok:
        return
    ok, detail, tools = run_bundle_handshake(layout.binary, layout.manifest)
    runner.case("packaged_bundle_handshake", ok, detail, tools=tools)


# ── 케이스 2: 오프라인 시작 ─────────────────────────────────────────────────


def case_offline(runner: Runner) -> None:
    """인터넷이 없어도 기동은 되고, 검색은 정직하게 실패한다.

    `AGK_SEARCH_OFFLINE=1` 은 probe 를 대신하는 명시 스위치다(실제 네트워크를 끊지 않고도 같은
    경로를 재기 위해서다 — 스위치와 실제 오프라인은 **같은 분기**를 탄다).
    """
    from antigravity_k.tools.ssak_search_provider import (
        NETWORK_UNAVAILABLE,
        classify_error_code,
        network_available,
    )
    from antigravity_k.tools.ssak_search_status import availability_snapshot

    os.environ["AGK_SEARCH_OFFLINE"] = "1"
    try:
        runner.case(
            "offline_probe_reports_no_network",
            network_available(force_probe=True) is False,
            "AGK_SEARCH_OFFLINE=1 → network_available() is False",
        )

        # 기동: 상태 조회는 네트워크 없이도 답한다(startup 이 실패하면 안 된다).
        snapshot = availability_snapshot()
        runner.case(
            "offline_status_answers",
            bool(snapshot.get("label")),
            f"availability={snapshot.get('availability')} label={snapshot.get('label')}",
        )

        # 검색: child 를 부른 **뒤** 실패하고(오프라인 캐시 응답을 막지 않는다), 그 실패는
        # NETWORK_UNAVAILABLE · permanent 다(legacy 로 대체되지 않는다).
        class _TransientRuntime:
            """자식이 네트워크 때문에 실패한 상황을 그대로 흉내낸다."""

            def call_tool(self, name: str, arguments: object, **_: object) -> object:
                class _Outcome(str):
                    is_error = True
                    error_code = "TRANSPORT_LOST"

                return _Outcome("search child failed: connection refused")

        from antigravity_k.tools.ssak_bundle_store import resolve_bundle
        from antigravity_k.tools.ssak_search_provider import SsakSearchSettings, search_with_bundled_provider

        resolution = resolve_bundle()
        artifact = str(resolution.layout.binary) if resolution.layout else None
        if artifact is None:
            runner.case("offline_search_fails_honestly", False, resolution.reason or "no bundle to point at")
            return
        # child 는 실제로 띄우지 않는다(스텁 런타임) — 재는 것은 **설정·분류·대체 정책**이다.
        settings = SsakSearchSettings(enabled=True, artifact_path=artifact)
        attempt = search_with_bundled_provider("오프라인 질의", settings=settings, runtime=_TransientRuntime())
        runner.case(
            "offline_search_fails_honestly",
            attempt.ok is False and attempt.error_code == NETWORK_UNAVAILABLE,
            f"ok={attempt.ok} error_code={attempt.error_code} fallback_allowed={attempt.transient}",
            failure_class=classify_error_code(attempt.error_code),
        )
        runner.case(
            "offline_search_does_not_fall_back",
            classify_error_code(NETWORK_UNAVAILABLE) == "permanent" and attempt.transient is False,
            "NETWORK_UNAVAILABLE 은 permanent 로 분류된다 — legacy 로 대체하지 않는다",
        )
    finally:
        os.environ.pop("AGK_SEARCH_OFFLINE", None)


# ── 케이스 3: 갱신·rollback ─────────────────────────────────────────────────


def _write_candidate(
    root: Path, binary_bytes: bytes, *, name: str, arch: str = "arm64", mode: int = 0o755
) -> tuple[Path, Path]:
    """갱신 후보 한 벌(바이너리 + 매니페스트)을 만든다. 해시는 **측정값**으로 적는다."""
    import hashlib

    binary = root / name / "bin" / BINARY_NAME
    binary.parent.mkdir(parents=True, exist_ok=True)
    binary.write_bytes(binary_bytes)
    binary.chmod(mode)
    manifest = root / name / "release" / "ssak-search-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "artifact": {
                    "sha256": hashlib.sha256(binary_bytes).hexdigest(),
                    "size_bytes": len(binary_bytes),
                    "platform": "darwin",
                    "arch": arch,
                    "format": "macho",
                },
                "product": {"name": "ssak-mcp-standalone", "version": "2.9.1-test"},
            }
        ),
        encoding="utf-8",
    )
    return binary, manifest


def case_rollback(runner: Runner, real_binary: Path) -> None:
    from antigravity_k.tools.ssak_bundle_store import (
        CODE_SELFTEST_FAILED,
        CODE_SHA_MISMATCH,
        CODE_UNTRUSTED,
        CODE_WRONG_ARCH,
        VERSIONS_DIRNAME,
        commit_update,
        current_version_dir,
        read_pointer,
        rollback,
        stage_update,
    )

    work = Path(tempfile.mkdtemp(prefix="ssak15-rollback-"))
    store = work / "store"
    os.environ["AGK_SSAK_STORE_DIR"] = str(store)
    # 갱신 소스가 신뢰 루트 안에 있어야 한다(밖이면 매니페스트가 거절된다 — 그게 다음 케이스다).
    os.environ["AGK_SEARCH_TRUSTED_ROOTS"] = os.pathsep.join([str(work), str(REPO)])

    real_bytes = real_binary.read_bytes()
    v1_binary, v1_manifest = _real_pair(real_binary)
    # v2 는 **같은 실물 바이트**를 다른 버전 라벨로 올린다(바이트가 같아도 승격·rollback 기계는
    # 그대로 재어진다). 바이트 자체가 어긋나는 경우는 truncated/selftest 케이스가 맡는다.
    v2_binary, v2_manifest = _write_candidate(work, real_bytes, name="v2")

    try:
        # 3-a: v1 을 설치한다(현재 버전이 생긴다).
        staged = stage_update(v1_binary, v1_manifest, root=store)
        committed = commit_update(staged, root=store) if staged.ok else None
        runner.case(
            "update_installs_v1",
            bool(staged.ok and committed and committed.committed),
            f"{staged.detail} / {committed.detail if committed else 'no commit'}",
            version=staged.version,
        )
        if not (staged.ok and committed and committed.committed):
            return
        v1_version = staged.version

        # 3-b: 잘린 다운로드 — sha 가 어긋나므로 거절되고 저장소는 그대로다.
        truncated = work / "truncated" / BINARY_NAME
        truncated.parent.mkdir(parents=True, exist_ok=True)
        truncated.write_bytes(real_bytes[: 1 << 20])
        truncated.chmod(0o755)
        staged_bad = stage_update(truncated, v2_manifest, root=store)
        runner.case(
            "update_refuses_truncated_download",
            (not staged_bad.ok) and staged_bad.code == CODE_SHA_MISMATCH,
            f"code={staged_bad.code} detail={staged_bad.detail[:90]}",
        )

        # 3-c: 다른 아키텍처 — sha 는 맞지만 호스트와 다르다.
        payload = json.loads(v2_manifest.read_text(encoding="utf-8"))
        payload["artifact"]["arch"] = "x64"
        wrong_arch_manifest = work / "v2" / "release" / "ssak-search-manifest-x64.json"
        wrong_arch_manifest.write_text(json.dumps(payload), encoding="utf-8")
        staged_arch = stage_update(v2_binary, wrong_arch_manifest, root=store)
        runner.case(
            "update_refuses_wrong_arch",
            (not staged_arch.ok) and staged_arch.code == CODE_WRONG_ARCH,
            f"code={staged_arch.code} detail={staged_arch.detail}",
        )

        # 3-d: 신뢰 밖 매니페스트 — 신뢰 루트 밖이고 **핀과도 다른** 바이트를 기술하면 거절된다.
        #      (핀과 같은 sha 를 기술한 매니페스트는 고정 릴리스의 복구이므로 어디서든 허용된다 — 그건
        #      3-a 의 정상 경로가 이미 덮는다. 여기서는 임의 다운로드를 흉내내야 한다.)
        arbitrary_binary, arbitrary_manifest = _write_candidate(
            work, b"#!/bin/sh\necho not-the-pinned-bytes\n", name="arbitrary"
        )
        outside = Path(tempfile.mkdtemp(prefix="ssak15-outside-"))
        try:
            outside_manifest = outside / "ssak-search-manifest.json"
            outside_manifest.write_text(arbitrary_manifest.read_text(encoding="utf-8"), encoding="utf-8")
            staged_untrusted = stage_update(arbitrary_binary, outside_manifest, root=store)
        finally:
            shutil.rmtree(outside, ignore_errors=True)
        runner.case(
            "update_refuses_untrusted_manifest",
            (not staged_untrusted.ok) and staged_untrusted.code == CODE_UNTRUSTED,
            f"code={staged_untrusted.code} detail={staged_untrusted.detail[-80:]}",
        )

        # 3-e: 실행은 되지만 실패하는 바이트 — selftest 가 막는다.
        failing_binary, failing_manifest = _write_candidate(work, b"#!/bin/sh\nexit 7\n", name="failing")
        staged_failing = stage_update(failing_binary, failing_manifest, root=store)
        runner.case(
            "update_refuses_a_candidate_that_fails_its_selftest",
            (not staged_failing.ok) and staged_failing.code == CODE_SELFTEST_FAILED,
            f"code={staged_failing.code} detail={staged_failing.detail}",
        )

        # 3-f: 갱신 도중 죽는다 — 스테이징까지만 하고 커밋을 부르지 않는다(그 사이 크래시와 같다).
        staged_v2 = stage_update(v2_binary, v2_manifest, root=store, expected_version="v2-test")
        runner.case("update_stages_v2", staged_v2.ok, staged_v2.detail, version=staged_v2.version)
        pointer = read_pointer(store) or {}
        runner.case(
            "crash_before_commit_keeps_previous_version",
            str(pointer.get("version", "")) == v1_version,
            f"current={pointer.get('version')} (스테이징만 되고 승격되지 않았다)",
        )
        current_dir = current_version_dir(store)
        if current_dir is None:
            runner.case("previous_version_still_runs", False, "current version directory vanished")
        else:
            ok, detail, _tools = run_bundle_handshake(
                current_dir / "bin" / BINARY_NAME,
                current_dir / "release" / "ssak-search-manifest.json",
            )
            runner.case("previous_version_still_runs", ok, detail)

        # 3-g: 실행 중 child 가 있으면 승격을 **보류**한다(실행 중 바이너리를 갈아끼우지 않는다).
        deferral = _live_child_deferral(store, staged_v2)
        runner.case(
            "update_defers_while_a_child_is_running",
            deferral[0],
            deferral[1],
            children=deferral[2],
        )

        # 3-h: 승격 → 현재가 v2 → rollback 하면 v1 로 돌아오고 다시 실행된다.
        committed_v2 = commit_update(staged_v2, root=store)
        runner.case(
            "update_promotes_v2",
            committed_v2.committed and committed_v2.version == "v2-test",
            committed_v2.detail,
            previous=committed_v2.previous_version,
        )
        rolled = rollback(root=store)
        runner.case("rollback_restores_v1", rolled.ok and rolled.version == v1_version, rolled.detail)
        restored = current_version_dir(store)
        if restored is None:
            runner.case("rolled_back_version_runs", False, "rolled-back version directory vanished")
        else:
            ok, detail, _tools = run_bundle_handshake(
                restored / "bin" / BINARY_NAME,
                restored / "release" / "ssak-search-manifest.json",
            )
            runner.case("rolled_back_version_runs", ok, detail)

        versions = sorted(p.name for p in (store / VERSIONS_DIRNAME).iterdir() if p.is_dir())
        runner.case("previous_version_directory_is_kept", len(versions) >= 2, f"보관된 버전: {versions}")
    finally:
        shutil.rmtree(work, ignore_errors=True)
        os.environ.pop("AGK_SSAK_STORE_DIR", None)
        os.environ.pop("AGK_SEARCH_TRUSTED_ROOTS", None)


def _live_child_deferral(store: Path, staged: StageResult) -> tuple[bool, str, list[int]]:
    """현재 버전으로 **실제 child 를 띄운 채** 승격을 시도한다 → 보류되어야 한다.

    이 케이스가 문장을 실행 가능한 형태로 만든다: "실행 중 child 의 바이너리를 갈아끼우지 않는다".
    실제로 child 가 돌고 있는 동안 포인터가 바뀌면, 다음 검색부터 다른 바이트가 답한다.
    """
    from antigravity_k.tools.ssak_bundle_store import commit_update, current_version_dir
    from antigravity_k.tools.ssak_search_runtime import (
        SearchRuntimeConfig,
        resolve_ssak_search_runtime,
        shutdown_ssak_search_runtime,
    )

    current = current_version_dir(store)
    if current is None:
        return False, "no current version to hold a child with", []

    # **호스트 싱글턴**을 쓴다 — 보류 판단이 보는 대상이 바로 그 싱글턴이기 때문이다(시험용 사본을
    # 따로 만들면 "보류되지 않았다"는 거짓 실패가 난다: 실제로 그 실수를 여기서 겪었다).
    # 앞선 상태 조회가 이미 싱글턴을 만들어 뒀을 수 있으므로 `replace_when_idle` 로 **의도한 설정**을
    # 가리키게 한다(child 가 없을 때만 교체되므로 진행 중 검색을 죽이지 않는다).
    runtime = resolve_ssak_search_runtime(
        SearchRuntimeConfig(
            artifact_path=str(current / "bin" / BINARY_NAME),
            manifest_path=str(current / "release" / "ssak-search-manifest.json"),
            ready_timeout_seconds=120.0,
        ),
        replace_when_idle=True,
    )
    try:
        if not runtime.ensure_ready(timeout=120.0):
            return False, f"child did not start: {runtime.status()}", []
        children = list(runtime.child_pids())
        if not children:
            return False, "the runtime reports no child pid, so the deferral was not exercised", []
        outcome = commit_update(staged, root=store)
        if outcome.committed:
            return False, f"the swap went ahead while a child was running: {outcome.detail}", children
        return outcome.deferred, outcome.detail, children
    finally:
        shutdown_ssak_search_runtime(timeout=30.0)


def _real_pair(binary: Path) -> tuple[Path, Path]:
    """실물 바이너리 + 그 옆의 매니페스트(설치 패키지 배치)."""
    manifest = binary.parent.parent / "release" / "ssak-search-manifest.json"
    return binary, manifest


# ── 케이스 4: 클린룸(설치 패키지만으로) ─────────────────────────────────────


def case_clean_room(runner: Runner) -> None:
    """W 체크아웃을 **참조하지 않는** 임시 환경에서 S wheel 만으로 handshake 를 한다."""
    work = Path(tempfile.mkdtemp(prefix="ssak15-cleanroom-"))
    try:
        wheel_dir = work / "dist"
        build = subprocess.run(
            ["uv", "build", "--wheel", "--out-dir", str(wheel_dir)],
            cwd=str(REPO),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
        )
        if build.returncode != 0:
            runner.case("clean_room_wheel_build", False, f"uv build failed: {build.stderr.strip()[-200:]}")
            return
        wheels = sorted(wheel_dir.glob("*.whl"))
        runner.case("clean_room_wheel_build", bool(wheels), f"built {[w.name for w in wheels]}")

        venv = work / "venv"
        created = subprocess.run(
            ["uv", "venv", str(venv), "--python", sys.executable],
            capture_output=True,
            text=True,
            timeout=300,
            check=False,
        )
        if created.returncode != 0:
            runner.case("clean_room_venv", False, created.stderr.strip()[-200:])
            return
        python = venv / "bin" / "python"
        installed = subprocess.run(
            ["uv", "pip", "install", "--python", str(python), str(wheels[-1])],
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        runner.case("clean_room_install", installed.returncode == 0, installed.stderr.strip()[-200:] or "installed")

        probe = work / "probe.py"
        probe.write_text(_CLEAN_ROOM_PROBE, encoding="utf-8")
        env = {
            key: value
            for key, value in os.environ.items()
            if key
            not in {
                "AGK_SSAK_BUNDLE_DIR",
                "AGK_SSAK_STORE_DIR",
                "AGK_SEARCH_TRUSTED_ROOTS",
                "AGK_SEARCH_SSAK_ARTIFACT_PATH",
                "AGK_SEARCH_MANIFEST",
                "PYTHONPATH",
            }
        }
        ran = subprocess.run(
            [str(python), str(probe)],
            cwd=str(work),  # repo 밖에서 실행한다 — 설치본이 스스로 찾아야 한다
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
            env=env,
        )
        last = (ran.stdout or ran.stderr).strip().splitlines()
        runner.case(
            "clean_room_handshake_uses_only_the_installed_package",
            ran.returncode == 0,
            last[-1] if last else f"exit={ran.returncode}",
            output=last[-3:],
        )

        # Node/Bun 이 **없는** PATH 로 같은 handshake 를 다시 한다. 가드는 probe 안에 있다 — PATH 에
        # node/bun 이 새어 들어오면 이 케이스는 실패한다. 그러지 않으면 "런타임이 없어서 통과"와
        # "런타임이 필요 없어서 통과"를 구별할 수 없다.
        no_node = work / "probe_nonode.py"
        no_node.write_text(_NO_NODE_PROBE, encoding="utf-8")
        bare = {"PATH": "/usr/bin:/bin"}
        for key in ("HOME", "TMPDIR", "LANG", "LC_ALL"):
            if key in os.environ:
                bare[key] = os.environ[key]
        ran_bare = subprocess.run(
            [str(python), str(no_node)],
            cwd=str(work),
            capture_output=True,
            text=True,
            timeout=600,
            check=False,
            env=bare,
        )
        last_bare = (ran_bare.stdout or ran_bare.stderr).strip().splitlines()
        runner.case(
            "clean_room_runs_without_node_or_bun",
            ran_bare.returncode == 0,
            last_bare[-1] if last_bare else f"exit={ran_bare.returncode}",
            path=bare["PATH"],
        )
    finally:
        shutil.rmtree(work, ignore_errors=True)


_NO_NODE_PROBE = '''"""Node/Bun 이 없는 PATH 에서 설치본만으로 handshake 한다(전제를 먼저 검사한다)."""
import json, os, shutil, sys
from pathlib import Path

leaked = [name for name in ("node", "nodejs", "bun", "npx") if shutil.which(name)]
assert not leaked, f"PATH 에 런타임이 있다 — 이 케이스는 아무것도 증명하지 못한다: {leaked}"
print(json.dumps({"path": os.environ.get("PATH"), "runtime_binaries_found": []}))

from antigravity_k.tools.ssak_bundle_store import resolve_bundle  # noqa: E402
from antigravity_k.tools.ssak_search_runtime import (  # noqa: E402
    SearchRuntimeConfig,
    SsakSearchRuntime,
)

resolution = resolve_bundle()
assert resolution.found, resolution.reason
layout = resolution.layout
runtime = SsakSearchRuntime(
    SearchRuntimeConfig(
        artifact_path=str(layout.binary),
        manifest_path=str(layout.manifest),
        ready_timeout_seconds=90.0,
    )
)
try:
    assert runtime.ensure_ready(timeout=90.0), runtime.status()
    tools = [tool.get("name") for tool in runtime.list_tools(timeout=60.0)]
    assert tools, "tools/list was empty"
    print(json.dumps({"tools": tools}))
finally:
    status = runtime.shutdown(timeout=30.0)
    assert not (status or {}).get("child_pids"), f"children left: {status}"

prefix = Path(sys.prefix).resolve()  # macOS: /var/folders → /private/var/folders 로 해석된다
assert str(layout.binary.resolve()).startswith(str(prefix)), "binary came from outside the install"
print("no node/bun needed")
'''


_CLEAN_ROOM_PROBE = '''"""설치된 S 패키지만으로 번들을 찾아 handshake 한다 — W 체크아웃은 참조하지 않는다."""
import json, sys
from pathlib import Path

from antigravity_k.tools.ssak_bundle_store import resolve_bundle
from antigravity_k.tools.ssak_search_runtime import SearchRuntimeConfig, SsakSearchRuntime

resolution = resolve_bundle()
assert resolution.found, resolution.reason
layout = resolution.layout
prefix = Path(sys.prefix).resolve()
inside = str(layout.binary.resolve()).startswith(str(prefix))
print(json.dumps({"binary": str(layout.binary), "venv_prefix": str(prefix), "inside_install": inside}))

runtime = SsakSearchRuntime(SearchRuntimeConfig(artifact_path=str(layout.binary), manifest_path=str(layout.manifest), ready_timeout_seconds=90.0))
try:
    assert runtime.ensure_ready(timeout=90.0), runtime.status()
    tools = [tool.get("name") for tool in runtime.list_tools(timeout=60.0)]
    assert tools, "tools/list was empty"
    print(json.dumps({"tools": tools, "inside_install": inside}))
finally:
    status = runtime.shutdown(timeout=30.0)
    assert not (status or {}).get("child_pids"), f"children left: {status}"

assert inside, "the resolved artifact did not come from the installed package"
print("clean-room ok")
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--offline-start", action="store_true", help="오프라인 기동·정직한 실패 케이스를 실행")
    parser.add_argument("--rollback-test", action="store_true", help="갱신·거절·크래시·rollback 케이스를 실행")
    parser.add_argument("--clean-room", action="store_true", help="wheel → 새 venv 만으로 handshake 검증(느림)")
    parser.add_argument("--bundle-dir", type=Path, default=None, help="검사할 번들 디렉터리(기본: 패키지/저장소)")
    parser.add_argument("--json", action="store_true", help="기계가 읽는 출력")
    args = parser.parse_args()

    runner = Runner(as_json=args.json)
    started = time.time()
    if not args.json:
        print(f"번들 검증 (repo={REPO})")

    case_packaged(runner, args.bundle_dir)
    if args.offline_start:
        case_offline(runner)
    if args.rollback_test:
        from antigravity_k.tools.ssak_bundle_store import resolve_bundle

        explicit = args.bundle_dir / "bin" / BINARY_NAME if args.bundle_dir else None
        resolution = resolve_bundle(explicit)
        if not resolution.found or resolution.layout is None:
            runner.case("rollback_test", False, resolution.reason or "no bundle to update from")
        else:
            case_rollback(runner, resolution.layout.binary)
    if args.clean_room:
        case_clean_room(runner)

    code = runner.finish()
    if not args.json:
        print(f"(소요 {time.time() - started:.1f}s)")
    return code


if __name__ == "__main__":
    sys.exit(main())
