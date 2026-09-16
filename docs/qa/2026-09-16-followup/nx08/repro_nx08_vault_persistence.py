#!/usr/bin/env python3
"""NX-08 — vault 영속화·복구의 미확인 의혹을 **재현해서** 판정한다.

규칙(카드 §4 NX-08):
  * 실제 사용자 vault 를 쓰지 않는다. 임시 Git repo 만 만든다.
  * 성공 경로를 monkeypatch 한 단위 테스트만으로 crash-safe 를 선언하지 않는다 —
    프로세스를 **실제로 죽이고**(SIGKILL) 그 뒤의 파일 hash·lock state·API 결과·Git 상태를 관측한다.
  * 각 의혹을 CONFIRMED / NOT_REPRODUCED / INCONCLUSIVE 로 판정하고 raw evidence 를 남긴다.
    미재현은 "결함 없음"으로 일반화하지 않고 그 시험 조건을 적는다.

사용:
    PYTHONPATH=src .venv/bin/python docs/qa/2026-09-16-followup/nx08/repro_nx08_vault_persistence.py --label before

종료 코드: 0 = 측정 완료(판정은 결과에), 2 = 계측 실패.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[4]

# `--src` 로 **어느 나무의 엔진을 잰는지** 정한다(기본: 작업 트리). before 는 `git archive HEAD src`
# 추출본을 가리켜 같은 자·다른 나무로 비교한다.
SRC_OVERRIDE: str | None = None

# 사용자 데이터 보호: config 의 경로를 임시 디렉터리로 돌린다(모듈 import 전에 설정해야 한다 —
# wiki.py 가 import 시점에 config.paths.* 를 상수로 굳힌다).
_SCRATCH = Path(tempfile.mkdtemp(prefix="nx08-scratch-"))
os.environ["AGK_PATH_DATA_DIR"] = str(_SCRATCH / "data")
os.environ["AGK_PATH_WIKI_DIR"] = str(_SCRATCH / "wiki")
os.environ["AGK_PATH_VECTORS_DIR"] = str(_SCRATCH / "vectors")
os.environ["AGK_PATH_LOGS_DIR"] = str(_SCRATCH / "logs")


def src_root() -> str:
    """측정 대상 엔진 소스 루트. `--src` 가 있으면 그쪽, 없으면 저장소 src."""
    return SRC_OVERRIDE or str(REPO_ROOT / "src")


sys.path.insert(0, src_root())

from antigravity_k.engine.vault import VaultEngine  # noqa: E402

CHILD_SCRIPT = textwrap.dedent(
    '''
    """SIGKILL 시나리오: write_note 가 파일을 자른 뒤 fsync 지점에서 죽는다."""
    import os
    import sys

    sys.path.insert(0, sys.argv[2])

    def die_on_fsync(fd):  # noqa: ANN001, ARG001
        os._exit(9)  # SIGKILL 에 준하는 즉시 종료 — 정리 코드(락 해제)가 실행되지 않는다

    os.fsync = die_on_fsync

    from antigravity_k.engine.vault import VaultEngine

    engine = VaultEngine(sys.argv[1], sync_rag=False)
    engine.write_note(sys.argv[4], {"title": "crash"}, sys.argv[3], commit_message="crash")
    print("UNREACHABLE")
    '''
)


def sha(text: str | bytes) -> str:
    data = text.encode("utf-8") if isinstance(text, str) else text
    return hashlib.sha256(data).hexdigest()


class Probe:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.root.mkdir(parents=True, exist_ok=True)

    def vault(self, name: str) -> VaultEngine:
        return VaultEngine(str(self.root / name), sync_rag=False)


def verdict(probe_id: str, question: str, status: str, **observed: Any) -> dict[str, Any]:
    return {"id": probe_id, "question": question, "verdict": status, "observed": observed}


# --------------------------------------------------------------------------- Q-A: fsync 실패


def probe_fsync_failure(probe: Probe) -> dict[str, Any]:
    engine = probe.vault("fsync")
    note = Path(engine.vault_path) / "note.md"
    engine.write_note("note.md", {"title": "v1"}, "BODY-V1\n", commit_message="v1")
    before_bytes = note.read_bytes()
    before_hash = sha(before_bytes)
    head_v1 = _git(engine.vault_path, "rev-parse", "HEAD")

    real_fsync = os.fsync

    def broken_fsync(fd: int) -> None:  # noqa: ARG001
        raise OSError(28, "No space left on device (주입)")

    os.fsync = broken_fsync
    raised = ""
    try:
        engine.write_note("note.md", {"title": "v2"}, "BODY-V2\n", commit_message="v2")
    except Exception as exc:  # noqa: BLE001 — 무엇이 올라오는지 자체가 관측 대상이다
        raised = f"{type(exc).__name__}: {exc}"
    finally:
        os.fsync = real_fsync

    after_bytes = note.read_bytes()
    preserved = after_bytes == before_bytes
    head_after = _git(engine.vault_path, "rev-parse", "HEAD")
    return verdict(
        "A1-fsync-failure",
        "fsync 가 실패하면 이전 bytes 가 보존되는가?",
        "NOT_REPRODUCED" if preserved else "CONFIRMED",
        previous_sha256=before_hash,
        after_sha256=sha(after_bytes),
        previous_bytes=before_bytes.decode("utf-8", "replace"),
        after_bytes=after_bytes.decode("utf-8", "replace"),
        error_surfaced=raised,
        git_head_before=head_v1,
        git_head_after=head_after,
        git_still_has_previous=_git_show_has_content(engine.vault_path, head_v1, "note.md", before_bytes),
        note="fsync 실패 시 이전 bytes 보존 = False 이면 CONFIRMED(비원자적 저장).",
    )


def probe_crash_mid_write(probe: Probe) -> dict[str, Any]:
    """프로세스를 실제로 죽여 자른 뒤 죽는 창(window)을 만든다."""
    engine = probe.vault("crash")
    note = Path(engine.vault_path) / "crash-note.md"
    engine.write_note("crash-note.md", {"title": "v1"}, "BODY-V1\n", commit_message="v1")
    before_hash = sha(note.read_bytes())

    lock_after_crash = run_killed_child(engine.vault_path, "crash-note.md", "BODY-V2\n")
    after_bytes = note.read_bytes()
    return verdict(
        "A2-crash-mid-write",
        "쓰기 도중 프로세스가 죽으면 이전 bytes 가 보존되는가?",
        "NOT_REPRODUCED" if sha(after_bytes) == before_hash else "CONFIRMED",
        previous_sha256=before_hash,
        after_sha256=sha(after_bytes),
        after_bytes=after_bytes.decode("utf-8", "replace")[:200],
        git_commits=_git(engine.vault_path, "log", "--oneline"),
        **lock_after_crash,
    )


# --------------------------------------------------------------------------- Q-B: lock 회복


def lock_timeout(engine: VaultEngine) -> float | None:
    for attribute in ("timeout", "_timeout"):
        value = getattr(engine._file_lock, attribute, None)
        if isinstance(value, int | float):
            return float(value)
    return None


def probe_lock_after_kill(probe: Probe) -> dict[str, Any]:
    engine = probe.vault("lock")
    engine.write_note("n.md", {"title": "v1"}, "v1\n", commit_message="v1")
    lock_path = Path(engine.vault_path) / ".git" / ".agk_vault.lock"
    product_timeout = lock_timeout(engine)

    crash = run_killed_child(engine.vault_path, "n.md", "v2\n")
    lock_left = lock_path.exists()
    lock_bytes = lock_path.stat().st_size if lock_left else None

    # 실제 제품 상수(30초)를 기다리지 않고 **차단 사실**을 재려면 스레드로 밀고 3초만 본다.
    outcome: dict[str, Any] = {}

    def attempt() -> None:
        try:
            engine.write_note("n.md", {"title": "v2"}, "v2\n", commit_message="v2")
            outcome["result"] = "wrote"
        except Exception as exc:  # noqa: BLE001 — 차단/타임아웃 타입이 관측 대상이다
            outcome["result"] = f"{type(exc).__name__}: {exc}"

    worker = threading.Thread(target=attempt, daemon=True)
    worker.start()
    worker.join(timeout=3.0)
    blocked = worker.is_alive()

    # 카드 rollback 절차: 남은 lock 파일을 제거하면 회복되는가?
    lock_path.unlink(missing_ok=True)
    worker.join(timeout=60.0)
    recovered = outcome.get("result")

    return verdict(
        "B1-lock-after-sigkill",
        "프로세스가 죽은 뒤 lock 이 영구 방해하는가?",
        "CONFIRMED" if lock_left and blocked else "NOT_REPRODUCED",
        child_exit=crash["child_exit"],
        child_stderr=crash["child_stderr"],
        lock_file_left_behind=lock_left,
        lock_file_bytes=lock_bytes,
        product_lock_timeout_s=product_timeout,
        blocked_after_3s=blocked,
        blocked_attempt_outcome=outcome.get("result"),
        self_healed=False if blocked else True,
        after_manual_unlink=recovered,
        recovery_procedure="`.git/.agk_vault.lock` 수동 제거 후 재시도",
        note_bytes_after_crash=(Path(engine.vault_path) / "n.md").read_text(encoding="utf-8")[:120],
        filelock_version=_filelock_version(),
    )


def run_killed_child(vault_path: Path, note: str, body: str) -> dict[str, Any]:
    """자식 프로세스가 write_note 도중 fsync 지점에서 죽는다(정리 코드 미실행)."""
    child = _SCRATCH / f"nx08_child_{note.replace('/', '_')}.py"
    child.write_text(CHILD_SCRIPT, encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = src_root()
    started = time.time()
    result = subprocess.run(
        [sys.executable, str(child), str(vault_path), src_root(), body, note],
        capture_output=True,
        text=True,
        env=env,
        timeout=120,
    )
    return {
        "child_exit": result.returncode,
        "child_stdout": result.stdout.strip(),
        "child_stderr": result.stderr.strip()[-400:],
        "elapsed_s": round(time.time() - started, 3),
    }


def _filelock_version() -> str:
    import filelock

    return getattr(filelock, "__version__", "unknown")


# --------------------------------------------------------------------------- Q-C: frontmatter


def probe_frontmatter(probe: Probe) -> list[dict[str, Any]]:
    engine = probe.vault("frontmatter")
    results: list[dict[str, Any]] = []

    lf = "---\ntitle: T\n---\nbody\n---\nrule\n"
    crlf = "---\r\ntitle: T\r\ntags:\r\n  - a\r\n---\r\nbody\r\n"
    eof_no_newline = "---\ntitle: T\n---"
    eof_with_newline = "---\ntitle: T\n---\n"
    malformed = "---\ntitle: [unclosed\n---\nbody\n"
    non_mapping = "---\n- a\n- b\n---\nbody\n"

    for name, text in (
        ("C1-lf", lf),
        ("C1-crlf", crlf),
        ("C2-eof-no-newline", eof_no_newline),
        ("C2-eof-with-newline", eof_with_newline),
        ("C3-malformed-yaml", malformed),
        ("C3-non-mapping", non_mapping),
    ):
        raised = ""
        metadata: Any = None
        body: Any = None
        try:
            metadata, body = engine.parse_markdown(text)
        except Exception as exc:  # noqa: BLE001 — 예외가 나는 것 자체가 관측 대상이다
            raised = f"{type(exc).__name__}: {exc}"
        results.append(
            verdict(
                name,
                "frontmatter 구분자·EOF·CRLF 를 올바르게 처리하는가?",
                "CONFIRMED" if raised or (name == "C1-crlf" and not metadata) else "NOT_REPRODUCED",
                exception=raised,
                metadata=dict(metadata) if isinstance(metadata, dict) else metadata,
                body_head=str(body)[:40] if body is not None else None,
                body_is_whole_input=body == text,
            )
        )

    # writer/reader 왕복 — 본문에 수평선이 있어도 frontmatter 가 유지되는가(회귀 확인)
    round_trip_meta = {"title": "RT", "tags": ["x"]}
    formatted = engine.format_markdown(round_trip_meta, "body\n---\nrule\n")
    parsed_meta, parsed_body = engine.parse_markdown(formatted)
    results.append(
        verdict(
            "C4-writer-reader-roundtrip",
            "format_markdown → parse_markdown 왕복이 frontmatter 를 보존하는가?",
            "NOT_REPRODUCED" if dict(parsed_meta) == round_trip_meta else "CONFIRMED",
            formatted=formatted,
            parsed_metadata=dict(parsed_meta),
            parsed_body=parsed_body,
        )
    )
    return results


# --------------------------------------------------------------------------- Q-D: 백업/복구


def probe_backup_restore(probe: Probe) -> dict[str, Any]:
    engine = probe.vault("restore")
    note = Path(engine.vault_path) / "note.md"
    engine.write_note("note.md", {"title": "T", "tags": ["a"], "schema": "v1"}, "ORIGINAL\n", commit_message="v1")
    os.chmod(note, 0o600)
    original_bytes = note.read_bytes()
    original_mode = stat.S_IMODE(note.stat().st_mode)
    snapshot = engine.create_snapshot("before edit")
    assert snapshot is not None, "스냅샷 생성 실패 — 측정 전제가 무너졌다"

    engine.write_note("note.md", {"title": "T"}, "MUTATED\n", commit_message="v2")
    mutated_bytes = note.read_bytes()

    restored = engine.restore_snapshot(snapshot, scope=["note.md"])
    after_bytes = note.read_bytes()
    after_mode = stat.S_IMODE(note.stat().st_mode)
    after_meta, _ = engine.read_note("note.md")

    return verdict(
        "D1-snapshot-restore",
        "백업/복구가 내용·schema 와 권한을 보존하는가?",
        "NOT_REPRODUCED" if after_bytes == original_bytes and after_mode == original_mode else "CONFIRMED",
        restore_returned=restored,
        snapshot_commit=snapshot,
        mutated_sha256=sha(mutated_bytes),
        content_preserved=after_bytes == original_bytes,
        schema_preserved=dict(after_meta) == {"title": "T", "tags": ["a"], "schema": "v1"},
        original_mode=oct(original_mode),
        after_mode=oct(after_mode),
        permissions_preserved=after_mode == original_mode,
    )


# --------------------------------------------------------------------------- Q-E: redact 경로


def probe_privacy_lock(probe: Probe) -> dict[str, Any]:
    engine = probe.vault("privacy")
    engine.write_note("secret.md", {"title": "S"}, "token = ABCDEF123456\n", commit_message="v1")

    from antigravity_k.engine.vault_privacy import apply_vault_privacy_mutation
    from antigravity_k.engine.vault_privacy_contracts import VaultPrivacyAction, VaultPrivacyMutation

    calls: list[str] = []

    class _Recorder:
        def __enter__(self) -> None:
            calls.append("enter")

        def __exit__(self, *args: object) -> bool:
            calls.append("exit")
            return False

    def acquire_lock() -> _Recorder:
        return _Recorder()

    mutation = VaultPrivacyMutation(
        action=VaultPrivacyAction.REDACT,
        paths=("secret.md",),
        values=("ABCDEF123456",),
    )
    result = apply_vault_privacy_mutation(
        vault_path=Path(engine.vault_path),
        acquire_lock=acquire_lock,
        resolve_path=engine._safe_resolve,  # noqa: SLF001 — 제품 경로를 그대로 쓴다
        mutation=mutation,
        sync_derivatives=lambda *args: None,
        is_safe_restore_target=engine._is_safe_restore_target,  # noqa: SLF001
    )
    after = (Path(engine.vault_path) / "secret.md").read_text(encoding="utf-8")
    return verdict(
        "E1-redact-lock",
        "마스킹(redact) 경로가 잠금 없이 파일을 덮어쓰는가? (NX-03 잔여 의혹 3)",
        "NOT_REPRODUCED" if calls == ["enter", "exit"] else "CONFIRMED",
        lock_calls=calls,
        replacement_count=result.replacement_count,
        content_after=after,
        secret_removed="ABCDEF123456" not in after,
    )


# --------------------------------------------------------------------------- Q-F/G: 미검증·정책


def probe_foreign_host_lock(probe: Probe) -> dict[str, Any]:
    """다른 호스트가 남긴 lock 파일은 자동 회복되는가? (파일시스템 경계의 실체)

    filelock 3.29 의 `SoftFileLock` 은 PID+호스트·이름을 lock 파일에 적고, 경합 시 **같은 호스트의
    죽은 PID** 만 곷는다. 그래서 다른 호스트 이름을 적어 같은 코드 경로를 국소 재현한다
    (NFS 자체는 이 호스트에 없어 마운트하지 않았다).
    """
    engine = probe.vault("foreign")
    engine.write_note("f.md", {"title": "v1"}, "v1\n", commit_message="v1")
    lock_path = Path(engine.vault_path) / ".git" / ".agk_vault.lock"
    lock_path.write_text(f"{os.getpid()}\nnot-this-host\n", encoding="utf-8")

    outcome: dict[str, Any] = {}

    def attempt() -> None:
        try:
            engine.write_note("f.md", {"title": "v2"}, "v2\n", commit_message="v2")
            outcome["result"] = "wrote"
        except Exception as exc:  # noqa: BLE001
            outcome["result"] = f"{type(exc).__name__}: {exc}"

    worker = threading.Thread(target=attempt, daemon=True)
    worker.start()
    worker.join(timeout=3.0)
    blocked = worker.is_alive()
    lock_path.unlink(missing_ok=True)
    worker.join(timeout=30.0)
    return verdict(
        "F2-foreign-host-stale-lock",
        "다른 호스트가 남긴 lock 은 자동으로 깨지는가? (NX-03 잔여 의혹 4 의 측정 가능한 부분)",
        "CONFIRMED" if blocked else "NOT_REPRODUCED",
        blocked_after_3s=blocked,
        outcome_after_manual_unlink=outcome.get("result"),
        only_same_host_dead_pid_is_broken="filelock 3.29 `SoftFileLock._try_break_stale_lock`: `hostname != socket.gethostname()` 면 return(깨지 않음)",
        nfs_mounted=False,
        reason="공유 파일시스템에서 다른 호스트가 죽으면 잔존 lock 이 유지될 수 있다 — 로컬에서 호스트명 위조로 코드 경로를 재현했다",
    )


def probe_environment(probe: Probe) -> list[dict[str, Any]]:
    fs = subprocess.run(["df", "-h", str(probe.root)], capture_output=True, text=True)
    tombstones = subprocess.run(
        ["grep", "-rn", "def .*tombstone.*(gc|cleanup|prune)", "-i", src_root()],
        capture_output=True,
        text=True,
    )
    return [
        verdict(
            "F1-nfs-flock-fsync",
            "NFS 등 비로컬 파일시스템에서 flock/fsync 가 신뢰할 수 있는가?",
            "INCONCLUSIVE",
            df_device=fs.stdout.strip().splitlines()[-1] if fs.stdout.strip() else "",
            reason="NFS 마운트가 이 호스트에 없다 — 로컬 파일시스템 관측을 다른 파일시스템으로 일반화하지 않는다(F2 가 코드상의 기대를 대신 쪼다)",
        ),
        verdict(
            "G1-tombstone-gc",
            "tombstone 누적에 GC 경로가 있는가? (NX-03 잔여 의혹 1)",
            "INCONCLUSIVE",
            gc_symbol_search=tombstones.stdout.strip() or "(없음)",
            reason="GC 심볼이 없다는 사실만 관측했다 — 정책 결정은 NX-03 후속/NX-08-F 로 남긴다",
        ),
    ]


# --------------------------------------------------------------------------- helpers


def _git(repo: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=False)
    return result.stdout.strip()


def _git_show_has_content(repo: Path, commit: str, path: str, expected: bytes) -> bool:
    result = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=repo, capture_output=True, check=False)
    return result.stdout == expected


# --------------------------------------------------------------------------- main


def run(label: str) -> dict[str, Any]:
    probe = Probe(Path(tempfile.mkdtemp(prefix=f"nx08-{label}-")))
    checks: list[dict[str, Any]] = [
        probe_fsync_failure(probe),
        probe_crash_mid_write(probe),
        probe_lock_after_kill(probe),
        *probe_frontmatter(probe),
        probe_backup_restore(probe),
        probe_privacy_lock(probe),
        probe_foreign_host_lock(probe),
        *probe_environment(probe),
    ]
    summary: dict[str, int] = {}
    for check in checks:
        summary[check["verdict"]] = summary.get(check["verdict"], 0) + 1
    report = {
        "check": "nx08_vault_persistence",
        "label": label,
        "owner_vault_touched": False,
        "scratch_root": str(probe.root),
        "verdict_tally": summary,
        "checks": checks,
    }
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description="NX-08 vault 영속화 의혹 측정")
    parser.add_argument("--label", default="run")
    parser.add_argument("--out", default="")
    parser.add_argument("--src", default="", help="측정할 엔진 소스 루트(기본: 저장소 src)")
    args = parser.parse_args()

    if args.src:
        globals()["SRC_OVERRIDE"] = args.src
        sys.path[:] = [entry for entry in sys.path if entry not in {str(REPO_ROOT / "src"), args.src}]
        sys.path.insert(0, args.src)
        for name in [key for key in sys.modules if key.startswith("antigravity_k")]:
            del sys.modules[name]
        globals()["VaultEngine"] = __import__("antigravity_k.engine.vault", fromlist=["VaultEngine"]).VaultEngine

    try:
        report = run(args.label)
    except Exception as exc:  # noqa: BLE001 — 계측 실패는 판정 실패와 구분한다
        print(json.dumps({"error": f"measurement failed: {exc}"}, ensure_ascii=False))
        return 2

    text = json.dumps(report, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)
    print(f"[{args.label}] {report['verdict_tally']}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    finally:
        shutil.rmtree(_SCRATCH, ignore_errors=True)
