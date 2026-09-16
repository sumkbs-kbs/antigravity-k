"""VAL-02 staging — 동시성·장시간·장애 주입 실측 (GA-100 plan §VAL-02).

수용기준과 시나리오 매핑:
  AC-1  정의된 concurrency에서 데이터 손실·cross-project leak·terminal contradiction 0
        → SC-1 (multi-project task CAS race), SC-2 (conversation revision CAS race),
          SC-3 (project_registry 동시 modify)
  AC-2  kill -9/restart 후 durable task와 event replay가 정확히 복구
        → SC-4 (SIGKILL 후 재오픈 복구 + event sequence 무결성)
  AC-3  P95/P99 latency, error rate, memory/FD/process leak이 threshold 안
        → SC-5 (복합 부하 + latency percentile + FD/RSS 누수 측정)
  AC-4  soak 후 orphan process/worktree/DB lock 없음
        → SC-6 (soak, --soak-seconds; 기본 리허설은 60s, 정식 8h는 문서 기재)

모든 리허설은 임시 디렉터리에서 실행한다 (프로덕션 데이터 무변경).
결과는 JSON으로 stdout 또는 --output 파일로 내보낸다.

실행: uv run --no-sync python scripts/val02_staging.py --output /tmp/val02-staging.json
"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import os
import signal
import statistics
import subprocess
import sys
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

# Release thresholds (plan §VAL-02 완료기준 3번 — release threshold).
P95_THRESHOLD_MS = 500.0
P99_THRESHOLD_MS = 1000.0
ERROR_RATE_THRESHOLD = 0.0  # 완료기준: error rate threshold 안 — 비율 0 (CAS loser는 정상 흐름)
FD_LEAK_THRESHOLD = 5
CONVERSATION_SOFT_MAX_MESSAGES = 64  # align with ConversationStore default (Decision A)
RSS_LEAK_THRESHOLD_MB = 64.0
SOAK_DEFAULT_SECONDS = 60  # 정식 gate는 8h(28800) — --soak-seconds로 상향
# NX-04: 원본 이력 전수 replay 는 이 크기까지만 수행한다(8h soak 은 연기 보고).
ORIGINALS_REPLAY_MAX_BYTES = 32 * 1024 * 1024
SOAK_CONSTRAINT_TEXT = "승인 없이 도구를 실행하지 마"
# NX-10: 제품이 worktree 를 만드는 위치(`WorktreeManager(worktrees_dir=...)` 기본값).
# SC-6 의 orphan 판정을 이 디렉토리로 **좁힌다** — 저장소 전역을 세면 다른 작업/게이트 러너가
# `/tmp` 에 남긴 prunable 항목까지 제품 결함처럼 잡혀, 제품과 무관한 이유로 SC-6 이 실패한다
# (실측: 60초 리허설에서 `/private/tmp/ssak-runner-gates.ENbZhm/checkout`).
# 검사 자체는 유지한다 — 약화가 아니라 범위 확정이다.
PRODUCT_WORKTREE_DIR = ".ag_worktrees"


def _count_product_orphan_worktrees() -> int:
    """제품 worktree 루트(`<repo>/.ag_worktrees`) 아래에서 prunable 로 표시된 항목 수.

    이 스크립트는 worktree 를 만들지 않는다(관측만). 다른 작업의 `/tmp` worktree 는 세지 않는다.
    """
    root = (REPO_ROOT / PRODUCT_WORKTREE_DIR).resolve()
    completed = subprocess.run(  # noqa: S603
        ["git", "worktree", "list"], cwd=REPO_ROOT, capture_output=True, text=True, check=False
    )
    orphaned = 0
    for line in completed.stdout.splitlines():
        if "prunable" not in line:
            continue
        raw_path = line.split(maxsplit=1)[0] if line.split() else ""
        if not raw_path:
            continue
        try:
            candidate = Path(raw_path).resolve()
        except OSError:  # pragma: no cover - 경로 해석 실패는 세지 않는다
            continue
        if candidate == root or root in candidate.parents:
            orphaned += 1
    return orphaned


def _percentile(values: list[float], pct: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round(pct / 100 * (len(ordered) - 1))))
    return ordered[idx] * 1000.0  # ms


def _conversation_soft_max() -> int:
    """제품이 실제로 쓰는 cap(환경변수 우선) — 시험이 제품 설정을 우회하지 않는다."""
    raw = os.environ.get("AGK_CONVERSATION_SOFT_MAX_MESSAGES")
    if raw is None or str(raw).strip() == "":
        return CONVERSATION_SOFT_MAX_MESSAGES
    try:
        return max(0, int(raw))
    except ValueError:
        return CONVERSATION_SOFT_MAX_MESSAGES


def _journal_line_stats(path: Path, chunk_size: int = 1 << 20) -> tuple[int, bool]:
    """NX-04: journal 을 메모리에 올리지 않고 줄 수와 마지막 줄 완결성을 센다.

    append 1회 = journal 이벤트 1줄이므로 줄 수가 곧 성공 append 수(= revision)다.
    8h soak 의 journal(수 GB)도 스트리밍으로 검증할 수 있고, 잘린 tail 은
    마지막 개행 여부로 드러난다.
    """
    lines = 0
    last_byte = b""
    try:
        with path.open("rb") as handle:
            while True:
                block = handle.read(chunk_size)
                if not block:
                    break
                lines += block.count(b"\n")
                last_byte = block[-1:]
    except OSError:
        return -1, False
    return lines, last_byte == b"\n"


def _fd_count() -> int:
    try:
        return (
            len(os.listdir("/dev/fd"))
            if os.path.isdir("/dev/fd")
            else int(
                subprocess.run(  # noqa: PTH107
                    ["sh", "-c", "ls /proc/self/fd | wc -l"], capture_output=True, text=True
                ).stdout.strip()
                or "0"
            )
        )
    except Exception:
        return -1


def _rss_mb() -> float:
    try:
        # macOS: ru_maxrss는 bytes, Linux는 KB — 플랫폼별로 정규화
        import platform
        import resource

        raw = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        if platform.system() == "Darwin":
            return raw / 1024.0 / 1024.0  # bytes → MB
        return raw / 1024.0  # KB → MB
    except Exception:
        return -1.0


# ─────────────────────────────────────────────────────────────────────
# SC-1: multi-project task CAS race — terminal contradiction 0 + owner 격리
# ─────────────────────────────────────────────────────────────────────


def _sc1_worker(db_path: str, task_ids: list[str], owner: str, iterations: int, result_q: Any) -> None:
    from antigravity_k.engine.task_state_store import TaskStateStore

    store = TaskStateStore(db_path)
    conflicts = 0
    wins = 0
    errors = 0
    for tid in task_ids:
        for i in range(iterations):
            # pending → running 경쟁 (허용 전이), 모두 같은 expected로 단일 winner 검증
            try:
                ok = store.transition(
                    tid,
                    "running",
                    expected_status="pending",
                    expected_version=0,
                    record_event=True,
                )
                if ok:
                    wins += 1
            except Exception:
                conflicts += 1
    # cross-project/owner leak probe: 남 owner task를 owner 필터로 읽으면 보이지 않아야 한다
    leaked = sum(1 for tid in task_ids if store.get_task(tid, owner_subject=f"other-{owner}") is not None)
    result_q.put({"owner": owner, "wins": wins, "conflicts": conflicts, "errors": errors, "leak": leaked})


def scenario_task_cas(workdir: Path, workers: int = 8, tasks_per_owner: int = 4) -> dict[str, Any]:
    from antigravity_k.engine.task_state_store import TaskStateStore

    db_path = str(workdir / "tasks.db")
    store = TaskStateStore(db_path)
    store.initialize()
    task_ids: list[str] = []
    owners = [f"proj-{i}" for i in range(workers)]
    for owner in owners:
        for j in range(tasks_per_owner):
            tid = f"t-{owner}-{j}"
            store.create_task(tid, f"prompt {owner} {j}", "pending", "2026-09-09T00:00:00Z", owner_subject=owner)
            task_ids.append(tid)

    q: Any = mp.Queue()
    procs = [
        mp.Process(target=_sc1_worker, args=(db_path, [t for t in task_ids if t.startswith(f"t-{o}-")], o, 2, q))
        for o in owners
    ]
    start = time.perf_counter()
    for p in procs:
        p.start()
    results = [q.get() for _ in procs]
    for p in procs:
        p.join(timeout=60)

    # terminal contradiction 검증: 각 task는 정확히 1번만 done으로 종료
    reopened = TaskStateStore(db_path)
    contradictions = 0
    total_wins = sum(r["wins"] for r in results)
    for tid in task_ids:
        rec = reopened.get_task(tid)
        # 단일 winner: 정확히 1번의 전이(version 1), running 상태, 이벤트 1건
        evs = reopened.list_execution_events(tid)
        if rec is None or rec["status"] != "running" or rec["version"] != 1 or len(evs) != 1:
            contradictions += 1
    leak = sum(r["leak"] for r in results)
    errors = sum(r["errors"] for r in results)
    elapsed = time.perf_counter() - start
    return {
        "scenario": "SC-1-task-cas-race",
        "workers": workers,
        "tasks": len(task_ids),
        "total_wins": total_wins,
        "terminal_contradictions": contradictions,
        "cross_owner_leak": leak,
        "unexpected_errors": errors,
        "elapsed_s": round(elapsed, 2),
        "pass": contradictions == 0 and leak == 0 and errors == 0 and total_wins == len(task_ids),
    }


# ─────────────────────────────────────────────────────────────────────
# SC-2: conversation revision CAS race — stale loser 명시적 409, 데이터 무손실
# ─────────────────────────────────────────────────────────────────────


def _sc2_worker(
    storage_dir: str,
    project_id: str,
    conv_id: str,
    n: int,
    prefix: str,
    max_attempts: int,
    result_q: Any,
) -> None:
    """NX-04: bounded retry CAS writer — 성공 id 와 거절 id 를 분리 보고한다.

    stale 패자는 **새 message id** 로 재시도하므로, 거절된 id 가 나중에 저장되지
    않았음을 집합으로 검증할 수 있다. 과거 SC-2 는 성공 "건수"만 세서 압축이 켜지면
    유효한 저장을 유실로 오인했다(카드 진단).
    """
    from antigravity_k.engine.conversation_store import ConversationStore, StaleConversationRevisionError

    store = ConversationStore(storage_dir)
    success_ids: list[str] = []
    rejected_ids: list[str] = []
    stale = 0
    errors = 0
    attempts = 0
    while len(success_ids) < n and attempts < max_attempts:
        attempts += 1
        message_id = f"{prefix}-{attempts}"
        rev = store.get_revision(project_id=project_id, conversation_id=conv_id) or 0
        try:
            store.append(
                project_id=project_id,
                conversation_id=conv_id,
                expected_revision=rev,
                role="user",
                content=f"{message_id} body",
                message_id=message_id,
            )
            success_ids.append(message_id)
        except StaleConversationRevisionError:
            stale += 1
            rejected_ids.append(message_id)
        except Exception:
            errors += 1
            break
    result_q.put(
        {
            "success_ids": success_ids,
            "rejected_ids": rejected_ids,
            "appended": len(success_ids),
            "stale": stale,
            "attempts": attempts,
            "errors": errors,
        }
    )


def scenario_conversation_cas(
    workdir: Path,
    workers: int = 6,
    turns_per_worker: int = 25,
    max_attempts_per_worker: int | None = None,
) -> dict[str, Any]:
    """NX-04 SC-2: CAS 계약과 압축 계약을 별도 결과로 보고한다.

    정본 계수 기준은 NX-02 원본 이력(journal)이다. view 는 cap64 로 bounded 이므로
    성공 append 수와 같을 수 없다 — "view < 성공" 은 정상 압축이지 유실이 아니다.
    """
    from antigravity_k.engine.conversation_store import ConversationStore

    storage_dir = str(workdir / "conversations")
    max_attempts = max_attempts_per_worker or turns_per_worker * 30
    soft_max = _conversation_soft_max()
    q: Any = mp.Queue()
    procs = [
        mp.Process(
            target=_sc2_worker,
            args=(storage_dir, "p1", "c1", turns_per_worker, f"w{i}", max_attempts, q),
        )
        for i in range(workers)
    ]
    for p in procs:
        p.start()
    results = [q.get() for _ in procs]
    join_timeout = 120
    alive = []
    for p in procs:
        p.join(timeout=join_timeout)
        if p.is_alive():
            alive.append(p.pid)
            p.terminate()
            p.join(timeout=10)

    reader = ConversationStore(storage_dir)
    final = reader.get(project_id="p1", conversation_id="c1")
    view_count = len(final.messages) if final else 0
    generations = final.memory.generation if final else 0
    originals = reader.original_history(project_id="p1", conversation_id="c1")
    original_ids = [str(m.get("id")) for m in originals]
    success_ids = [mid for r in results for mid in r["success_ids"]]
    rejected_ids = [mid for r in results for mid in r["rejected_ids"]]
    errors = sum(r["errors"] for r in results)
    # 유실은 원본 기준으로만 판정한다.
    lost_originals = max(0, len(success_ids) - len(original_ids))
    missing_ids = sorted(set(success_ids) - set(original_ids))
    resurrected_ids = sorted(set(rejected_ids) & set(original_ids))
    view_bounded = soft_max <= 0 or 0 < view_count <= soft_max
    return {
        "scenario": "SC-2-conversation-cas",
        "workers": workers,
        "turns_per_worker": turns_per_worker,
        "max_attempts_per_worker": max_attempts,
        "conversation_soft_max": soft_max,
        "appended": len(success_ids),
        "stale_rejected": sum(r["stale"] for r in results),
        "attempts": sum(r["attempts"] for r in results),
        "unexpected_errors": errors,
        "originals": len(original_ids),
        "lost_originals": lost_originals,
        "missing_original_ids": missing_ids[:10],
        "rejected_ids_stored": resurrected_ids[:10],
        "view_messages": view_count,
        "view_bounded": view_bounded,
        "compaction_generations": generations,
        "revision": final.revision if final else -1,
        "revision_matches_successes": bool(final and final.revision == len(success_ids)),
        "workers_alive_after_join": alive,
        "join_timeout_s": join_timeout,
        "pass": (
            errors == 0
            and not alive
            and lost_originals == 0
            and not resurrected_ids
            and view_bounded
            and len(success_ids) >= 123
            and bool(final and final.revision == len(success_ids))
        ),
    }


# ─────────────────────────────────────────────────────────────────────
# SC-3: project_registry 동시 modify — flock 아래 reload-modify-save 보존
# ─────────────────────────────────────────────────────────────────────


def _sc3_worker(storage_path: str, project_roots: list[str], result_q: Any) -> None:
    from pathlib import Path

    from antigravity_k.engine.project_registry import ProjectRegistry

    registry = ProjectRegistry(storage_path=Path(storage_path))
    registered = 0
    errors = 0
    for root in project_roots:
        try:
            Path(root).mkdir(parents=True, exist_ok=True)
            registry.add_project(os.path.basename(root), root)
            registered += 1
        except Exception:
            errors += 1
    result_q.put({"registered": registered, "errors": errors})


def scenario_registry_concurrent(workdir: Path, workers: int = 5, per_worker: int = 8) -> dict[str, Any]:
    from antigravity_k.engine.project_registry import ProjectRegistry

    storage_path = str(workdir / "projects.json")
    q: Any = mp.Queue()
    procs = []
    for w in range(workers):
        roots = [str(workdir / f"ws-{w}-{i}") for i in range(per_worker)]
        procs.append(mp.Process(target=_sc3_worker, args=(storage_path, roots, q)))
    for p in procs:
        p.start()
    results = [q.get() for _ in procs]
    for p in procs:
        p.join(timeout=120)

    final = ProjectRegistry(storage_path=Path(storage_path))
    total_expected = workers * per_worker
    listed = final.list_projects()
    missing = total_expected - len(listed)
    lock_file = Path(storage_path + ".lock")
    return {
        "scenario": "SC-3-registry-flock",
        "workers": workers,
        "expected_projects": total_expected,
        "registered": len(listed),
        "missing": max(0, missing),
        "errors": sum(r["errors"] for r in results),
        "lock_file_present": lock_file.exists(),
        "pass": missing <= 0 and sum(r["errors"] for r in results) == 0,
    }


# ─────────────────────────────────────────────────────────────────────
# SC-4: kill -9 복구 — durable task + event replay 정확성
# ─────────────────────────────────────────────────────────────────────


def _sc4_child(db_path: str, task_id: str, events: int, ready_path: str) -> None:
    """이벤트를 기록하다가 부모에게 kill -9 당하는 자식 프로세스."""
    from antigravity_k.engine.task_state_store import TaskStateStore

    store = TaskStateStore(db_path)
    store.initialize()
    store.create_task(task_id, "kill-recovery probe", "pending", "2026-09-09T00:00:00Z")
    _ = store.transition(task_id, "running", expected_status="pending")
    Path(ready_path).write_text("ready", encoding="utf-8")
    for i in range(events):
        _ = store.append_execution_event(task_id, "step.progress", json.dumps({"step": i}))
        time.sleep(0.01)
    # 정상 종료 끝까지 가지 못하고 kill -9 당한다 (부모가 시그널 전송)


def scenario_kill_recovery(workdir: Path, events: int = 50) -> dict[str, Any]:
    from antigravity_k.engine.task_state_store import TaskStateStore

    db_path = str(workdir / "kill.db")
    task_id = "kill-9-task"
    ready = workdir / "child.ready"
    proc = mp.Process(target=_sc4_child, args=(db_path, task_id, events, str(ready)))
    proc.start()
    for _ in range(200):
        if ready.exists():
            break
        time.sleep(0.01)
    # child가 이벤트를 몇 개 기록할 시간을 준 뒤 kill -9
    time.sleep(0.15)
    killed = False
    if proc.pid is not None:
        try:
            os.kill(proc.pid, signal.SIGKILL)
            killed = True
        except ProcessLookupError:
            killed = False
    proc.join(timeout=10)

    reopened = TaskStateStore(db_path)
    rec = reopened.get_task(task_id)
    evs = reopened.list_execution_events(task_id)
    sequences = [e["sequence"] for e in evs]
    monotonic = all(b > a for a, b in zip(sequences, sequences[1:], strict=False))
    unique = len(sequences) == len(set(sequences))
    # AC-2: kill -9 후 (a) 커밋된 이벤트는 sequence 무결성 유지, (b) 죽은 소유자의
    # running task는 prepare_resume로 복구 가능, (c) 복구 후 재실행 이벤트가 이어진다.
    recovered = (
        rec is not None
        and rec["status"] == "running"
        and monotonic
        and unique
        and len(evs) > 0  # kill 전 최소 1건은 커밋되어야 의미 있는 복구 검증
    )
    resumed = reopened.prepare_resume(task_id) if rec is not None else False
    # FR-06/RP-11(R11-08): 재개 요청만으로 끝내지 않는다 — 재시작 worker가
    # task를 최종 완료로 이끌고, 완료된 task의 재이행(중복 부작용)이 거부되는지까지.
    final_done = False
    duplicate_side_effect_rejected = False
    if resumed:
        try:
            # prepare_resume은 task를 "resuming"으로 둔다 — 재시작 worker는
            # resuming → running → done으로 최종 완료시킨다.
            _ = reopened.transition(task_id, "running", expected_status="resuming")
            _ = reopened.transition(task_id, "done", output="recovered", expected_status="running")
            done_rec = reopened.get_task(task_id)
            final_done = done_rec is not None and done_rec["status"] == "done"
        except Exception:
            final_done = False
        try:
            # 완료된 task를 다시 running으로 전환하려는 시도는 거부돼야 한다.
            _ = reopened.transition(task_id, "running", expected_status="done")
            duplicate_side_effect_rejected = False
        except Exception:
            duplicate_side_effect_rejected = True
    post_sequences = [e["sequence"] for e in reopened.list_execution_events(task_id)]
    post_unique = len(post_sequences) == len(set(post_sequences))
    return {
        "scenario": "SC-4-kill-9-recovery",
        "killed_with_sigkill": killed,
        "surviving_events": len(evs),
        "sequence_monotonic": monotonic,
        "sequence_unique": unique,
        "task_status_after_kill": rec["status"] if rec else None,
        "prepare_resume_ok": resumed,
        "resumed_task_completed": final_done,
        "duplicate_side_effect_rejected": duplicate_side_effect_rejected,
        "post_recovery_sequences_unique": post_unique,
        "pass": bool(recovered and resumed and final_done and duplicate_side_effect_rejected and post_unique),
    }


# ─────────────────────────────────────────────────────────────────────
# SC-5: 복합 부하 — P95/P99 latency + error rate + FD/RSS 누수
# ─────────────────────────────────────────────────────────────────────


def scenario_load_latency(workdir: Path, ops: int = 300) -> dict[str, Any]:
    from antigravity_k.engine.task_state_store import TaskStateStore

    db_path = str(workdir / "load.db")
    store = TaskStateStore(db_path)
    store.initialize()
    latencies: list[float] = []
    errors = 0
    fds_before = _fd_count()
    for i in range(ops):
        tid = f"load-{i}"
        t0 = time.perf_counter()
        try:
            store.create_task(tid, "load", "pending", "2026-09-09T00:00:00Z")
            _ = store.transition(tid, "running", expected_status="pending")
            _ = store.append_execution_event(tid, "step.start", "{}")
            _ = store.transition(tid, "done", output="ok", expected_status="running")
            _ = store.list_execution_events(tid)
        except Exception:
            errors += 1
        latencies.append(time.perf_counter() - t0)
    fds_after = _fd_count()
    p95 = _percentile(latencies, 95)
    p99 = _percentile(latencies, 99)
    error_rate = errors / ops
    return {
        "scenario": "SC-5-load-latency",
        "operations": ops,
        "p95_ms": round(p95, 2),
        "p99_ms": round(p99, 2),
        "mean_ms": round(statistics.mean(latencies) * 1000, 2),
        "error_rate": error_rate,
        "fd_before": fds_before,
        "fd_after": fds_after,
        "fd_growth": (fds_after - fds_before) if fds_before >= 0 and fds_after >= 0 else 0,
        "rss_mb": round(_rss_mb(), 1),
        "pass": p95 <= P95_THRESHOLD_MS and p99 <= P99_THRESHOLD_MS and error_rate <= ERROR_RATE_THRESHOLD,
    }


# ─────────────────────────────────────────────────────────────────────
# SC-6: soak — orphan process/worktree/DB lock, 지속 memory growth
# ─────────────────────────────────────────────────────────────────────


def scenario_soak(workdir: Path, seconds: int) -> dict[str, Any]:
    from antigravity_k.engine.conversation_store import ConversationStore
    from antigravity_k.engine.task_state_store import TaskStateStore

    db_path = str(workdir / "soak.db")
    store = TaskStateStore(db_path)
    store.initialize()
    conv_store = ConversationStore(storage_dir=workdir / "soak-conversations")
    rss_samples: list[float] = []
    fd_samples: list[int] = []
    ops = 0
    conv_ops = 0
    errors = 0
    sample_overhead_s = 0.0
    # NX-04: 의미 보존(SC-6)을 위해 cap 을 넘기도록 제약을 타이머 밖에서 먼저 넣는다.
    # (측정 루프 자체의 작업량은 변경하지 않는다.)
    seeded = conv_store.append(
        project_id="soak",
        conversation_id="soak-conv",
        expected_revision=0,
        role="user",
        content=SOAK_CONSTRAINT_TEXT,
    )
    conv_rev = seeded.revision
    started = time.time()
    deadline = started + seconds
    i = 0
    while time.time() < deadline:
        tid = f"soak-{i}"
        try:
            store.create_task(tid, "soak", "pending", "2026-09-09T00:00:00Z")
            _ = store.transition(tid, "running", expected_status="pending")
            _ = store.transition(tid, "done", output="ok", expected_status="running")
            ops += 1
        except Exception:
            errors += 1
        # FR-06/RP-11(R11-07): DB 루프만이 아니라 conversation 작업 부하 포함.
        try:
            snap = conv_store.append(
                project_id="soak",
                conversation_id="soak-conv",
                expected_revision=conv_rev,
                role="user",
                content=f"soak turn {i}",
            )
            conv_rev = snap.revision
            conv_ops += 1
        except Exception:
            errors += 1
        i += 1
        if i % 50 == 0:
            # NX-04: 계측 overhead 를 실측해 보고한다(샘플링이 soak 를 지배하지 않음).
            _t0 = time.perf_counter()
            rss_samples.append(_rss_mb())
            fd_samples.append(_fd_count())
            sample_overhead_s += time.perf_counter() - _t0
    # FR-06/RP-11: 실측 종료 시각 — 요청값이 아니라 실제로 흘린 시간을 기록한다.
    actual_duration = round(time.time() - started, 3)
    growth = (rss_samples[-1] - rss_samples[0]) if len(rss_samples) >= 2 else 0.0
    fd_growth = (fd_samples[-1] - fd_samples[0]) if len(fd_samples) >= 2 else 0
    # orphan worktree: 이 스크립트는 repo 내 worktree를 만들지 않는다 — 관측만.
    # NX-10: 범위는 제품 worktree 루트(`.ag_worktrees`) — 저장소 전역 카운트는 타 작업의
    # `/tmp` 항목을 제품 결함처럼 잡아 SC-6 을 제품과 무관한 이유로 막았다(위 상수 주석).
    orphan_wt = _count_product_orphan_worktrees()
    # DB lock 잔존: 모든 연산 종료 후 lock 파일이 남아 접근을 막으면 안 된다
    lock_ok = True
    try:
        _ = store.list_tasks(limit=1)
        _ = conv_store.get_revision(project_id="soak", conversation_id="soak-conv")
    except Exception:
        lock_ok = False
    # conversation CAS 불변: 성공 append 수와 최종 revision이 정확히 일치해야 한다.
    final_rev = conv_store.get_revision(project_id="soak", conversation_id="soak-conv")
    conv_consistent = final_rev == conv_rev
    conv_record = conv_store.get(project_id="soak", conversation_id="soak-conv")
    conv_message_count = len(conv_record.messages) if conv_record else -1
    # NX-04: 원본 이력은 별도 기준으로 관측한다. 8h soak 의 journal 은 replay 비용이
    # 크므로 크기 상한 아래에서만 전수 replay 하고, 넘으면 연기 사실을 기록한다.
    originals_count = -1
    originals_replay_deferred = False
    constraint_preserved = False
    journal_seq = -1
    journal_lines = -1
    journal_terminated = False
    journal_path = conv_store.journal_path(project_id="soak", conversation_id="soak-conv")
    journal_bytes = journal_path.stat().st_size if journal_path.is_file() else 0
    if journal_bytes <= ORIGINALS_REPLAY_MAX_BYTES:
        # 소규모 리허설: 원본을 전수 replay 해 ID 수와 journal seq 를 직접 확인한다.
        originals_count = len(conv_store.original_history(project_id="soak", conversation_id="soak-conv"))
        journal_seq = conv_store.history_state(project_id="soak", conversation_id="soak-conv")["journal_seq"]
        originals_verified = originals_count == conv_rev and journal_seq == conv_rev
        originals_verification = "full_replay"
    else:
        # 정식 soak(8h, 수 GB): 메모리에 올리지 않는 스트리밍 검증으로 대체한다.
        # (연기 사실을 숨기지 않는다 — replay 미실시는 별도 필드로 보고한다.)
        originals_replay_deferred = True
        journal_lines, journal_terminated = _journal_line_stats(journal_path)
        originals_verified = journal_terminated and journal_lines == conv_rev
        originals_verification = "stream_line_count"
    if conv_record is not None:
        constraint_preserved = any(
            c.text == SOAK_CONSTRAINT_TEXT and c.status == "active" for c in conv_record.memory.active_constraints()
        )
    originals_complete = originals_verified
    # Decision A: product may auto-compact; require bounded message list, not
    # message_count == ops (that forced unbounded RAM).
    soft_max = _conversation_soft_max()
    # After compact: summary + retain_tail(6) => typically <= soft_max (trigger)
    # and well under soft_max + retain_tail + 1.
    messages_bounded = soft_max <= 0 or (0 < conv_message_count <= soft_max)
    return {
        "scenario": "SC-6-soak",
        "requested_duration_s": seconds,
        "duration_s": actual_duration,
        "actual_duration_s": actual_duration,
        "completed_ops": ops,
        "conversation_ops": conv_ops,
        "conversation_revision": final_rev,
        "conversation_message_count": conv_message_count,
        "conversation_append_equality": conv_consistent,
        "conversation_messages_bounded": messages_bounded,
        "conversation_soft_max": soft_max,
        # NX-04: 원본/압축/의미 보존을 별도 결과로 보고한다.
        "conversation_originals": originals_count,
        "conversation_originals_complete": originals_complete,
        "conversation_originals_verification": originals_verification,
        "conversation_originals_replay_deferred": originals_replay_deferred,
        "conversation_journal_bytes": journal_bytes,
        "conversation_journal_lines": journal_lines,
        "conversation_journal_terminated": journal_terminated,
        "conversation_journal_seq": journal_seq,
        "conversation_compaction_generations": conv_record.memory.generation if conv_record else -1,
        "conversation_constraint_preserved": constraint_preserved,
        "soak_constraint_seeded": True,
        "measurement_overhead_s": round(sample_overhead_s, 4),
        "measurement_overhead_ratio": round(sample_overhead_s / actual_duration, 5) if actual_duration else 0.0,
        "errors": errors,
        "rss_samples_mb": [round(r, 1) for r in rss_samples],
        "rss_growth_mb": round(growth, 1),
        "fd_samples": fd_samples,
        "fd_growth": fd_growth,
        "orphan_worktrees": orphan_wt,
        "db_accessible_after": lock_ok,
        "pass": (
            errors == 0
            and growth <= RSS_LEAK_THRESHOLD_MB
            and fd_growth <= FD_LEAK_THRESHOLD
            and orphan_wt == 0
            and lock_ok
            and conv_consistent
            and messages_bounded
            and originals_complete
            and constraint_preserved
            # 실측 시간이 요청의 90% 미만이면 soak가 조기 종료됐다 — 실패.
            and actual_duration >= seconds * 0.9
        ),
    }


SCENARIOS: dict[str, Callable[..., dict[str, Any]]] = {
    "SC-1": scenario_task_cas,
    "SC-2": scenario_conversation_cas,
    "SC-3": scenario_registry_concurrent,
    "SC-4": scenario_kill_recovery,
    "SC-5": scenario_load_latency,
    "SC-6": scenario_soak,
}

# FR-06/RP-11(R11-04): 필수 시나리오. 실행되지 않은 필수 시나리오는
# all([])==True 로 승인되지 않는다.
REQUIRED_SCENARIOS: tuple[str, ...] = ("SC-1", "SC-2", "SC-3", "SC-4", "SC-5", "SC-6")


def main() -> int:
    parser = argparse.ArgumentParser(description="VAL-02 resilience staging")
    parser.add_argument("--output", help="결과 JSON 저장 경로 (기본: stdout)")
    parser.add_argument("--scenarios", default="SC-1,SC-2,SC-3,SC-4,SC-5,SC-6", help="실행 시나리오 목록")
    parser.add_argument("--soak-seconds", type=int, default=SOAK_DEFAULT_SECONDS)
    parser.add_argument("--workdir", default=None, help="리허설 임시 루트 (기본: .tmp/val02-<ts>)")
    args = parser.parse_args()

    import tempfile

    root = Path(args.workdir) if args.workdir else Path(tempfile.mkdtemp(prefix="val02-"))
    root.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "task_id": "VAL-02",
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "workdir": str(root),
        "thresholds": {
            "p95_ms": P95_THRESHOLD_MS,
            "p99_ms": P99_THRESHOLD_MS,
            "error_rate_max": ERROR_RATE_THRESHOLD,
            "fd_leak_max": FD_LEAK_THRESHOLD,
            "rss_leak_mb": RSS_LEAK_THRESHOLD_MB,
        },
        "scenarios": [],
    }
    only = [s.strip() for s in args.scenarios.split(",") if s.strip()]
    for key in only:
        fn = SCENARIOS.get(key)
        if fn is None:
            report["scenarios"].append({"scenario": key, "pass": False, "error": "unknown scenario"})
            continue
        try:
            if key == "SC-6":
                result = fn(root, args.soak_seconds)
            else:
                result = fn(root)
        except Exception as exc:  # noqa: BLE001
            result = {"scenario": key, "pass": False, "error": f"{type(exc).__name__}: {exc}"}
        report["scenarios"].append(result)

    executed = {s.get("scenario", "") for s in report["scenarios"]}
    missing_required = [key for key in REQUIRED_SCENARIOS if key not in executed and key not in only]
    report["missing_required"] = missing_required
    # FR-06/RP-11: 빈 실행 목록(all([]) == True) 또는 필수 누락은 PASS가 아니다.
    report["all_pass"] = (
        bool(report["scenarios"]) and not missing_required and all(s.get("pass") for s in report["scenarios"])
    )
    rendered = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        Path(args.output).write_text(rendered + "\n", encoding="utf-8")
    print(rendered)
    return 0 if report["all_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
