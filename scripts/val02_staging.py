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
import cProfile
import json
import multiprocessing as mp
import os
import pstats
import queue as queue_module
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
# worker 결과 대기 상한(초). 왜 필요한가 (2026-09-17 실측): `q.get()` 에 타임아웃이 없어서
# SC-3 의 worker 가 `RegistrySaveError` 로 죽자 부모가 **영원히** 기다렸고, 8시간 soak 이
# 아무 산출물 없이 멈춰 있었다(러너는 종료 시에만 리포트를 쓴다 — 결과 0). worker 가 죽는 것과
# 실행 전체가 멈추는 것은 **다른 사건**이다: 이제 타임아웃은 그 실행의 오류로 세고 계속 간다
# ("돌렸는데 틀렸다" 가 "돌다가 아무것도 안 남겼다" 보다 낫다). `AGK_VAL02_WORKER_TIMEOUT_S` 로 조정.
WORKER_RESULT_TIMEOUT_S = float(os.environ.get("AGK_VAL02_WORKER_TIMEOUT_S", "120"))

RSS_LEAK_THRESHOLD_MB = 64.0
# SC-6 기준 재설계(2026-09-17 · 오너 질문 “워밍업 구간이 기준에 포함되는 게 맞나”):
# 옛 판정식 `마지막 표본 − 첫 표본` 은 첫 표본이 **루프 50 반복 뒤**라, 그 50 반복이 처리량에 따라
# 0.08초(600회/초)에서 20.45초(2.4회/초)까지 움직였다 — **같은 코드를 처리량에 따라 다르게 재는**
# 기준이었고, 그 워밍업이 예산의 15~33%를 먹었다. 이제 ① **워밍업 창 밖의 증가**를 64 MB 로 보고
# (연속성 유지) ② **반복당 creep** 을 함께 재서 처리량이 변해도 뜻이 유지되게 한다.
# 근거 수치·대안 비교: docs/qa/2026-09-16-followup/nx10/SC6_CRITERION_REVIEW.md
RSS_WARMUP_MIN_S = 300.0  # 창의 하한 — 1분 창은 종료 투영을 기울기 모델에 매단다(모델 분산 30~46%)
RSS_WARMUP_FRACTION = 0.05  # 8시간 → 1,440초(24분). 실측: 5분 이상이면 세 모델의 판정이 일치한다
RSS_CREEP_MAX_KB_PER_OP = 0.25  # 창 밖 반복당 상한 — 건강한 실행 0.004 KB/회 · 누수 24.5 KB/회(실측)
SOAK_DEFAULT_SECONDS = 60  # 정식 gate는 8h(28800) — --soak-seconds로 상향

# ── 처리량 회귀 축(2026-09-17 오너 지시) ───────────────────────────────────────
# 왜 별도 축인가: 8시간 실행이 **느려지는 것**과 **메모리가 새는 것**은 다른 사건인데 지금은 RSS 하나만 본다.
# 실측(2026-09-17 4차 실행 30분 블록): 벽시계 692→508 ops/s(**-26.5%**)인데 CPU 정규화 효율은 779.9→740.6
# ops/CPU초(**-5.0%**)였다 — 즉 벽시계 감소의 대부분은 **기계 경합/대기**이고 제품 항목은 5% 였다.
# 그래서 `벽시계 = 효율 × 이용률` 로 **분해해 원인을 귀속**한다(`THROUGHPUT_MAX_DECLINE` 은 그 전에 걸린다).
THROUGHPUT_MAX_DECLINE = 0.15  # 허용 감소 15% — 잡아야 하는 회귀는 27%, 건강한 실행 실측은 5~6%(여유 10%p)
THROUGHPUT_MIN_RUN_S = 7200.0  # 이보다 짧으면 분기 중앙값이 성립하지 않는다(60초 리허설은 판정 불가)
THROUGHPUT_BLOCK_MIN_S = 300.0  # 블록 하한(5분) — 10분 블록 실측 잡음 중앙 8.4%/최대 29.6%
THROUGHPUT_BLOCK_FRACTION = 0.02  # 8시간 → 576초(9.6분) 블록
THROUGHPUT_MIN_BLOCKS_PER_QUARTER = 3  # 분기당 블록 3개 미만이면 중앙값을 신뢰하지 않는다
THROUGHPUT_HOST_LOAD_MAX = 0.5  # load1/코어수 — 넘으면 “내 회귀”라 단정하지 않는다(재실행 요구)
THROUGHPUT_EFFICIENCY_FLAT = 0.95  # 효율이 이 이상 유지되면 벽시계 감소를 제품 탓으로 돌리지 않는다

# ── 처리량 회귀의 **귀속 사다리**(2026-09-17 오너 지시) ───────────────────────────
# 게이트는 “느려졌다”까지만 말한다. 다음 질문은 항상 같다: **어느 호출이** 느려졌나.
# 사다리는 한 반복을 국면(phase)으로 나누고, 각 국면의 **단가(µs/반복)** 를 같은 블록 추정량으로 재서
# 분기 사이 증가분을 국면별로 쪼갠다. 쪼갠 합은 총 증가분과 같아야 하므로(정체식) 잔차를 같이 남긴다.
#   ① 국면 하나가 증가분의 절반 이상  → 그 국면을 **이름으로 지목**(phase)
#   ② 증가가 국면들에 고르게 퍼짐      → 공통 경로를 본다(spread)
#   ③ 계측 밖(할당자·GC·인터프리터)    → 잔차가 크다(outside_phases) → 다음 칸은 프로세스 전체 프로파일
#   ④ 총 증가가 잡음 수준            → 지목하지 않는다(insufficient) — 없는 범인을 만들지 않는다
# 이 사다리는 **판정이 아니라 설명**이다: 초록 실행에는 돌지 않고(not_applicable), 빨간 판정을 바꾸지도 않는다.
ATTRIBUTION_DOMINANCE = 0.5  # 한 국면이 증가분의 절반 이상이면 지목한다(그 미만이면 “퍼졌다”)
ATTRIBUTION_MIN_DELTA_RATIO = 0.02  # 총 단가 증가가 첫 분기 단가의 2% 미만이면 “귀속할 증가 없음”(잡음)
ATTRIBUTION_SAMPLE_EVERY = int(os.environ.get("NX10_ATTRIBUTION_SAMPLE_EVERY", 500))  # 국면 CPU 스냅샷 간격
ATTRIBUTION_OUTSIDE_GAP_RATIO = 0.5  # 잔차가 총 증가분의 절반을 넘으면 “계측 밖”으로 귀속한다
# 한 반복은 이 국면들을 **순서대로** 지난다(이름은 리포트에 실려 다음 사람이 같은 쪼개기를 재현한다).
SOAK_PHASES: tuple[str, ...] = ("task.create", "task.transition", "conversation.append")

# ── 사다리의 **다음 칸**: 지목된 국면 **안**의 하위 단계(2026-09-17 오너 지시) ─────────────────
# 국면 이름까지 좁혀지면 다음 질문은 “그 국면 안에서 어느 단계인가”(예: `conversation.append` 안의
# 저널 한 줄 쓰기 · view 재작성 · tail) 다. 그 단계들은 **제품 코드 안**(`src/`)에 있어 경계 타이머를
# 심을 수 없다 — 그래서 하네스가 **창(window) 단위로 cProfile 을 걸어** 파이썬 수준 귀속을 얻는다.
#   · 창은 **국면 하나**만 계측한다(국면을 돌려 가며) — 그래야 “그 국면 안의 함수 순위”가 나온다
#   · 계측한 창의 반복은 **판정 계열에서 제외**한다(계측이 판정을 오염시키지 않는다 — §28 의 규칙)
#   · 오버헤드는 따로 **보고**한다(`deep_overhead_ratio`) — 측정기가 만든 몫을 숨기지 않는다
#   · 파이썬 프로파일러는 **C 확장을 못 본다**(sqlite·json C 인코더·커널 fsync). 그 몫은 잔차로 남기고
#     잔차가 크면 “파이썬 밖”이라 말한다(지어내지 않는다)
#   · 표본률은 8시간에서도 무시할 수준(기본 1/200 · 총 상한 1,000 반복 = 측정 계열의 0.006%)
DEEP_PROFILE_ENABLED = os.environ.get("NX10_DEEP_PROFILE", "1") != "0"
DEEP_SAMPLE_EVERY = int(os.environ.get("NX10_DEEP_SAMPLE_EVERY", 200))  # 몇 반복마다 창을 여는가
DEEP_WINDOW_CALLS = 25  # 한 창이 계측하는 **국면 호출 수**(전이는 반복당 2회라 반복 수와 다르다)
DEEP_MAX_WINDOWS = 40  # 창 상한(국면 3개에 고르게 돌려 간다)
DEEP_MAX_OPS = 1000  # 계측 반복 총 상한
DEEP_MIN_WINDOWS = 3  # 이보다 적으면 함수 순위를 말하지 않는다
DEEP_FUNCTION_DOMINANCE = 0.5  # 한 함수가 국면 안 시간의 절반 이상이면 그 이름을 지목한다
DEEP_OUTSIDE_RATIO = 0.5  # 파이썬 밖(C 확장·커널) 잔차가 국면 시간의 절반을 넘으면 “국면 밖”이라 말한다
DEEP_TOP_FUNCTIONS = 5  # 리포트에 싣는 상위 함수 수
# 계측기 자신(하네스 파일)의 프레임은 순위에서 **뺀다** — 안 빼면 첫 칸이 `val02_staging.py:<lambda>` 가 되어
# 사다리가 자기 자신을 지목한다(프로브가 실제로 그렸다). 뺀 몫은 `deep_instrument_us_per_op` 로 밝힌다.
DEEP_EXCLUDE_FILES: tuple[str, ...] = (Path(__file__).name,)

# ── 사다리의 **네 번째 칸**: 지목된 함수를 **어느 경로가 부르고, 반복당 몇 번** 부르는가(2026-09-17 오너 지시) ──
# 앞칸이 “`posix.fsync` 다”까지 말했다면 남는 질문은 둘이다 — **누가** 부르는가(**호출 경로**), 그리고
# **얼마나 자주** 부르는가. 둘은 처방을 가른다: 반복당 1회면 그 호출 자체를 싸게 만들어야 하고(정책·배치),
# 반복당 여러 번이면 **호출을 합쳐야** 한다(코얼레싱). 같은 함수·같은 시간이라도 다른 수술이다.
# 자료는 새로 계측할 필요가 없다 — `cProfile` 통계가 **호출자 표**(`callers`)를 이미 들고 있다.
PATH_MIN_CALLER_SHARE = 0.5  # 한 호출자가 그 함수 호출의 절반 이상이면 그 경로를 지목한다
PATH_TOP_CALLERS = 5  # 함수마다 리포트에 싣는 호출자 수(리포트 크기 상한)
PATH_MAX_DEPTH = 4  # 경로 사슬을 위로 걷는 최대 칸 수
PATH_REPEAT_PER_ITERATION = 1.5  # 반복당 이 이상이면 “여러 번”(한 번과 두 번의 경계를 1.5 로 둔다)
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


# ── 프레임 라벨: cProfile/pstats 가 주는 것을 **읽을 수 있는 키**로 바꾸는 단 하나의 자리 ────────────────
# 키 규칙: 파이썬 프레임은 `파일이름:함수이름`, 내장/C 프레임은 그 라벨 그대로(`'<built-in method posix.fsync>'`).
# 계약 시험의 픽스처가 이 규칙을 그대로 쓴다.
# `_lsprof` 는 자기 오버헤드를 `<method 'disable' of '_lsprof.Profiler' objects>` 라는 가짜 프레임으로
# 끼워 넣는다 — 이것도 **계측기**이므로 하네스 파일과 같이 순위에서 뺀다(뺐다고 밝힌다).
INSTRUMENT_FRAME_LABELS: tuple[str, ...] = ("<method 'disable' of '_lsprof.Profiler' objects>",)


def _frame_key(label: tuple[str, int, str]) -> tuple[str, str, int]:
    """pstats 라벨 `(파일, 행, 이름)` → `(키, 파일, 행)`.

    내장/C 프레임은 pstats 가 파일 자리를 `'~'` 로 준다(실측) — 그때는 그 라벨을 그대로 키로 쓴다.
    """
    filename, line, funcname = label
    if filename in ("", "~"):
        return funcname, "", int(line)
    return f"{Path(filename).name}:{funcname}", filename, int(line)


def _is_instrument_frame(key: str) -> bool:
    """계측기 자신(하네스 파일·`_lsprof` 가짜 프레임)인가 — 사다리가 자기 자신을 지목하지 않게 한다."""
    if key in INSTRUMENT_FRAME_LABELS:
        return True
    return Path(key.split(":", 1)[0]).name in DEEP_EXCLUDE_FILES


def _pstats_table(profile: cProfile.Profile) -> dict[Any, Any]:
    """cProfile 통계를 **호출자 표까지** 담긴 pstats 표로 꺼낸다.

    왜 `pstats` 를 거치는가: `Profile.getstats()` 의 6번째 칸은 **callees**(내가 부른 것)이고 호출자가
    아니다 — 거기서 호출 경로를 읽으려던 첫 구현은 내장 함수에서 `None` 을 만났다(프로브가 실측으로 잡음).
    `pstats.Stats` 가 그 callee 목록을 뒤집어 caller 표를 만든다(`print_callers` 가 쓰는 그 자료다).

    ⚠ 두 가지를 알고 쓸 것:
      ① `Stats(profile)` 는 `profile.stats` 를 **비운다**(typeshed 에 `Stats.stats` 선언이 없어 `vars()` 로
         꺼내는데, 그 우회를 여기 한 곳에만 둔다).
      ② 한 프로파일러로 두 번 부르면 두 번째 표는 **빈다** — 그래서 창마다 새 `Profile` 을 쓴다.
    """
    table: dict[Any, Any] = vars(pstats.Stats(profile))["stats"]
    return table


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
    results, worker_timeouts = _collect_worker_results(
        q,
        procs,
        fallback={"owner": None, "wins": 0, "conflicts": 0, "errors": 1, "leak": 0},
    )
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
        "worker_timeouts": worker_timeouts,
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


def _collect_worker_results(
    result_q: Any, procs: list[Any], *, fallback: dict[str, Any]
) -> tuple[list[dict[str, Any]], int]:
    """worker 결과를 **제한 시간 안에** 걷는다(타임아웃은 오류 1건으로 세고 계속한다).

    반환: (결과 목록, 타임아웃 수). 타임아웃된 worker 에는 `fallback`(오류 1건을 포함해야 한다)
    을 넣고, 그 프로세스가 살아서 큐를 물고 있는 경우를 대비해 `terminate` 까지 간다 — 그러지
    않으면 다음 시나리오가 그 프로세스의 자원을 뺏어 측정이 오염된다.
    """
    results: list[dict[str, Any]] = []
    timeouts = 0
    for p in procs:
        try:
            results.append(result_q.get(timeout=WORKER_RESULT_TIMEOUT_S))
        except queue_module.Empty:
            timeouts += 1
            p.terminate()
            p.join(timeout=10)
            results.append(dict(fallback))
    return results, timeouts


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
    results, worker_timeouts = _collect_worker_results(
        q,
        procs,
        fallback={
            "success_ids": [],
            "rejected_ids": [],
            "appended": 0,
            "stale": 0,
            "attempts": 0,
            "errors": 1,
        },
    )
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
        "worker_timeouts": worker_timeouts,
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
    results, worker_timeouts = _collect_worker_results(q, procs, fallback={"registered": 0, "errors": 1})
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
        "worker_timeouts": worker_timeouts,
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


def sc6_warmup_window_s(actual_duration_s: float) -> float:
    """SC-6 워밍업 창(초) — 시작 비용(임포트·할당자·첫 압축)을 판정에서 빼는 구간.

    왜 `max(5분, 지속×5%)` 인가(실측 근거): 창을 1분으로 두면 같은 실행의 종료 투영이
    “요즘 기울기”와 “창 밖 평균”에 따라 **갈렸고**(모델 분산 = 기준의 30~46%), 창을 5분으로 두면
    세 모델이 일치했다. 더 늘리면 숫자 폭만 줄고 판정 구간을 잃는다.
    """
    return max(RSS_WARMUP_MIN_S, actual_duration_s * RSS_WARMUP_FRACTION)


def sc6_rss_criterion(
    rss_samples_mb: list[float],
    sample_ops: list[int],
    sample_times_s: list[float],
    actual_duration_s: float,
) -> dict[str, Any]:
    """SC-6 의 RSS 판정 — **워밍업 창 밖 증가**(P1)와 **반복당 creep**(P2) 두 축.

    반환 필드는 그대로 리포트에 실린다. `rss_growth_mb`(옛 값)도 함께 남긴다 — 판정에는 쓰지 않고
    회귀 비교·연속성용이다. 입력은 **리포트에 실리는 값과 같은 반올림**을 거친 목록을 쓴다(누구든
    `rss_samples_mb` 만으로 같은 판정을 재현할 수 있게).

    1 반복(operation) = DB task 3단계 + 대화 append 1회 — `scenario_soak` 의 루프 1회와 같다.
    """
    window_s = sc6_warmup_window_s(actual_duration_s)
    total_growth = (rss_samples_mb[-1] - rss_samples_mb[0]) if len(rss_samples_mb) >= 2 else 0.0
    fields: dict[str, Any] = {
        "rss_growth_mb": round(total_growth, 1),
        "rss_warmup_window_s": round(window_s, 1),
        "rss_warmup_fraction": RSS_WARMUP_FRACTION,
        "rss_warmup_min_s": RSS_WARMUP_MIN_S,
        "rss_creep_max_kb_per_op": RSS_CREEP_MAX_KB_PER_OP,
    }
    # 창이 실행 길이와 비슷하면 “워밍업을 뺀 증가”라는 값 자체가 없다 — 판정하지 않고 이유를 남긴다.
    # (60초 리허설이 여기로 온다: 1분 실행에 8시간 임계값을 물으면 +21 MB 를 누수처럼 보고한다.)
    if actual_duration_s < window_s * 2 or len(rss_samples_mb) < 3:
        fields.update(
            {
                "rss_warmup_index": -1,
                "rss_warmup_growth_mb": 0.0,
                "rss_growth_warmup_excluded_mb": 0.0,
                "rss_creep_kb_per_operation": 0.0,
                "rss_criterion": "not_applicable",
                "rss_criterion_basis": (
                    f"판정 불가: 실측 {actual_duration_s:.1f}s < 창 {window_s:.1f}s × 2 "
                    f"(표본 {len(rss_samples_mb)}개) — 이 구간의 증가는 누수가 아니라 시작 비용이다"
                ),
            }
        )
        return fields
    index = next((k for k, t in enumerate(sample_times_s) if t >= window_s), len(sample_times_s) - 1)
    if index >= len(rss_samples_mb) - 1:
        fields.update(
            {
                "rss_warmup_index": -1,
                "rss_warmup_growth_mb": 0.0,
                "rss_growth_warmup_excluded_mb": 0.0,
                "rss_creep_kb_per_operation": 0.0,
                "rss_criterion": "not_applicable",
                "rss_criterion_basis": (
                    f"판정 불가: 창 {window_s:.1f}s 뒤에 표본이 없다(표본 {len(rss_samples_mb)}개) — "
                    "샘플 간격을 줄이거나 실행을 늘려야 판정이 된다"
                ),
            }
        )
        return fields
    # 반올림은 **한 번만** 한다: 리포트에 실리는 값(0.1 MB 단위)과 같은 값으로 반복당 creep 까지
    # 계산해야, 다음 사람이 `rss_samples_mb` + `rss_warmup_index` 만으로 **같은 숫자를 재현**할 수 있다
    # (2026-09-17 리허설이 이 틈을 잡았다 — 반올림 전 값으로 계산하면 리포트와 1e-4 만큼 어긋났다).
    excluded_mb = round(rss_samples_mb[-1] - rss_samples_mb[index], 1)
    ops_after = max(sample_ops[-1] - sample_ops[index], 1)
    creep_kb_per_op = round(excluded_mb * 1024.0 / ops_after, 4)
    verdict = (
        "pass" if (excluded_mb <= RSS_LEAK_THRESHOLD_MB and creep_kb_per_op <= RSS_CREEP_MAX_KB_PER_OP) else "fail"
    )
    fields.update(
        {
            "rss_warmup_index": index,
            "rss_warmup_growth_mb": round(rss_samples_mb[index] - rss_samples_mb[0], 1),
            "rss_growth_warmup_excluded_mb": excluded_mb,
            "rss_creep_kb_per_operation": creep_kb_per_op,
            "rss_criterion": verdict,
            "rss_criterion_basis": (
                f"창 밖 증가 {excluded_mb:.1f} MB ≤ {RSS_LEAK_THRESHOLD_MB:.0f} MB "
                f"· 반복당 {creep_kb_per_op:.4f} KB ≤ {RSS_CREEP_MAX_KB_PER_OP} KB "
                f"(창 {window_s:.0f}s = 표본 {index}개 건너뜀 · 창 밖 반복 {ops_after:,}회)"
            ),
        }
    )
    return fields


def _median(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    middle = len(ordered) // 2
    return ordered[middle] if len(ordered) % 2 else (ordered[middle - 1] + ordered[middle]) / 2


def throughput_blocks(
    sample_ops: list[int],
    sample_times_s: list[float],
    sample_cpu_s: list[float],
    *,
    actual_duration_s: float,
) -> dict[str, Any]:
    """표본 계열을 **블록 중앙값** 삼중항으로 접는다 — (벽시계 ops/s, 효율 ops/CPU초, 이용률 CPU초/벽초).

    왜 중앙값인가: 60초 표본의 벽시계 처리량 변동은 실측 CV 16.8%(블록 편차 중앙 8.4% · 최대 29.6%)라
    두 점(처음/끝) 비교는 잡음에 진다. 블록 중앙값을 다시 분기로 묶으면 표본오차가 √블록 수 만큼 줄어
    “27% 감소”를 잡으면서 건강한 실행을 건드리지 않는다(분기 = 실행의 1/4).
    블록 크기 = `max(5분, 지속×2%)` — 8시간이면 9.6분으로 50개 블록, 분기당 12개다.
    """
    if len(sample_ops) < 4 or len(sample_cpu_s) != len(sample_ops) or len(sample_times_s) != len(sample_ops):
        return {"blocks": [], "block_s": 0.0, "window_s": sc6_warmup_window_s(actual_duration_s), "skipped": 0}
    window_s = sc6_warmup_window_s(actual_duration_s)
    block_s = max(THROUGHPUT_BLOCK_MIN_S, actual_duration_s * THROUGHPUT_BLOCK_FRACTION)
    buckets: dict[int, list[tuple[float, float, float]]] = {}
    skipped = 0
    for index in range(1, len(sample_ops)):
        start = sample_times_s[index - 1]
        span = sample_times_s[index] - start
        if span <= 0:
            continue
        if start < window_s or sample_times_s[index] < window_s:
            skipped += 1
            continue
        delta_ops = sample_ops[index] - sample_ops[index - 1]
        delta_cpu = sample_cpu_s[index] - sample_cpu_s[index - 1]
        if delta_ops <= 0 or delta_cpu <= 0:
            continue
        bucket = buckets.setdefault(int(sample_times_s[index] // block_s), [])
        bucket.append((delta_ops / span, delta_ops / delta_cpu, delta_cpu / span))
    blocks = [
        (
            round(_median([b[0] for b in sorted(values, key=lambda item: item[0])]), 3),
            round(_median([b[1] for b in values]), 3),
            round(_median([b[2] for b in values]), 5),
        )
        for _, values in sorted(buckets.items())
        if values
    ]
    return {"blocks": blocks, "block_s": round(block_s, 1), "window_s": round(window_s, 1), "skipped": skipped}


def throughput_criterion(
    sample_ops: list[int],
    sample_times_s: list[float],
    sample_cpu_s: list[float],
    sample_load1: list[float],
    cpu_count: int,
    actual_duration_s: float,
) -> dict[str, Any]:
    """SC-6 의 **처리량 회귀 판정** — RSS 와 독립인 축(2026-09-17 오너 지시).

    세 축을 동시에 낸다(정체성이 “벽시계 = 효율 × 이용률”):
      · 효율(`ops/CPU초`) = **제품 축** — 한 일당 비용이 늘었는가(기계 부하에 거의 안 흔들린다)
      · 벽시계(`ops/s`)   = **서비스 축** — 운영자가 겪는 것
      · 이용률(`CPU초/벽초`) = **진단 축** — 벽시계 감소가 “느려짐”인지 “덜 돌아감(경합/대기)”인지 가른다

    판정 규칙(실측 보정: 건강 −5.0% · 잡아야 하는 회귀 −27% · 허용 −15%):
      ① 효율이 `1−15%` 미만 → **fail**(제품 회귀 — 벽시계와 무관하게 잡는다)
      ② 벽시계만 `1−15%` 미만:
         · 호스트 부하(`load1/코어수`) > 0.5 → **not_applicable**(경합 — 다시 재야 한다. 통과가 아니다)
         · 부하가 낮다면 → **fail**(제품이 대기로 느려졌다 — I/O·lock 대기 증가)
      ③ 그 밖 → pass
    """
    rolled = throughput_blocks(sample_ops, sample_times_s, sample_cpu_s, actual_duration_s=actual_duration_s)
    blocks: list[tuple[float, float, float]] = rolled["blocks"]
    load_after = [value for value, at in zip(sample_load1, sample_times_s) if at >= rolled["window_s"] and value >= 0]
    load_ratio = round(_median(load_after) / cpu_count, 4) if load_after and cpu_count else -1.0
    fields: dict[str, Any] = {
        "throughput_block_s": rolled["block_s"],
        "throughput_blocks": len(blocks),
        "throughput_warmup_skipped": rolled["skipped"],
        "throughput_host_load_ratio": load_ratio,
        "throughput_max_decline": THROUGHPUT_MAX_DECLINE,
        "throughput_blocks_wall": [b[0] for b in blocks],
        "throughput_blocks_efficiency": [b[1] for b in blocks],
        "throughput_blocks_utilization": [b[2] for b in blocks],
    }
    if actual_duration_s < THROUGHPUT_MIN_RUN_S:
        fields.update(
            {
                "throughput_wall_ratio": 1.0,
                "throughput_efficiency_ratio": 1.0,
                "throughput_utilization_ratio": 1.0,
                "throughput_criterion": "not_applicable",
                "throughput_criterion_basis": (
                    f"판정 불가: 실측 {actual_duration_s:.0f}s < 최소 {THROUGHPUT_MIN_RUN_S:.0f}s —"
                    " 처리량 회귀는 8시간 규모에서만 뜻이 있다(60초 리허설은 시작 비용이 지배한다)"
                ),
            }
        )
        return fields
    quarter = max(THROUGHPUT_MIN_BLOCKS_PER_QUARTER, len(blocks) // 4)
    if len(blocks) < quarter * 2:
        fields.update(
            {
                "throughput_wall_ratio": 1.0,
                "throughput_efficiency_ratio": 1.0,
                "throughput_utilization_ratio": 1.0,
                "throughput_criterion": "not_applicable",
                "throughput_criterion_basis": (
                    f"판정 불가: 워밍업 창 밖 블록이 {len(blocks)}개(블록 {rolled['block_s']:.0f}s) —"
                    f" 분기마다 {THROUGHPUT_MIN_BLOCKS_PER_QUARTER}개 이상 필요하다(샘플 간격을 줄이거나 실행을 늘려야 한다)"
                ),
            }
        )
        return fields
    first, last = blocks[:quarter], blocks[-quarter:]
    wall_ratio = round(_median([b[0] for b in last]) / max(_median([b[0] for b in first]), 1e-9), 4)
    eff_ratio = round(_median([b[1] for b in last]) / max(_median([b[1] for b in first]), 1e-9), 4)
    util_ratio = round(_median([b[2] for b in last]) / max(_median([b[2] for b in first]), 1e-9), 4)
    floor = 1.0 - THROUGHPUT_MAX_DECLINE
    numbers = (
        f"벽시계 {_median([b[0] for b in first]):.0f}→{_median([b[0] for b in last]):.0f} ops/s({(wall_ratio - 1) * 100:+.1f}%)"
        f" · 효율 {_median([b[1] for b in first]):.0f}→{_median([b[1] for b in last]):.0f} ops/CPU초({(eff_ratio - 1) * 100:+.1f}%)"
        f" · 이용률 {(util_ratio - 1) * 100:+.1f}% · 부하 {load_ratio if load_ratio >= 0 else '모름'} (블록 {len(blocks)}개 · 창 {rolled['window_s']:.0f}s 제외)"
    )
    identity_gap = round(abs(wall_ratio - eff_ratio * util_ratio), 4)
    fields.update(
        {
            "throughput_wall_ratio": wall_ratio,
            "throughput_efficiency_ratio": eff_ratio,
            "throughput_utilization_ratio": util_ratio,
            "throughput_identity_gap": identity_gap,
            "throughput_wall_ops_per_s": round(_median([b[0] for b in last]), 1),
            "throughput_efficiency_ops_per_cpu_s": round(_median([b[1] for b in last]), 2),
            "throughput_utilization": round(_median([b[2] for b in last]), 5),
        }
    )
    if eff_ratio < floor:
        fields["throughput_criterion"] = "fail"
        fields["throughput_criterion_basis"] = (
            f"**제품 회귀**: 일당 비용이 {(1 - eff_ratio) * 100:.1f}% 늘었다(허용 {THROUGHPUT_MAX_DECLINE * 100:.0f}%)"
            f" — {numbers}"
        )
    elif wall_ratio < floor and load_ratio < 0:
        # 부하를 못 읽었으면 **어느 쪽으로도 단정하지 않는다**: “내 회귀”라고 하면 없는 결함을 만들고,
        # “경합”이라고 하면 진짜 회귀를 덮어 준다. 재실행이 답이다(`not_applicable` 은 통과가 아니다).
        fields["throughput_criterion"] = "not_applicable"
        fields["throughput_criterion_basis"] = (
            f"판정 불가(재실행 필요): 벽시계가 {(1 - wall_ratio) * 100:.1f}% 줄었는데 **부하 계기를 못 읽었다**"
            f"(load1 미지원 또는 표본 없음) — 효율은 유지됐다.{numbers}. "
            "호스트 부하를 함께 남기는 실행에서만 ‘경합’과 ‘대기’를 가를 수 있다."
        )
    elif wall_ratio < floor and load_ratio > THROUGHPUT_HOST_LOAD_MAX:
        fields["throughput_criterion"] = "not_applicable"
        fields["throughput_criterion_basis"] = (
            f"판정 불가(재실행 필요): 벽시계가 {(1 - wall_ratio) * 100:.1f}% 줄었지만 **효율은 유지**됐다"
            f"(제품 회귀 아님) — {numbers}. 호스트가 바빴다(load1/코어 {load_ratio:.2f} > {THROUGHPUT_HOST_LOAD_MAX})."
            " 조용한 기계에서 다시 재야 판정이 된다."
        )
    elif wall_ratio < floor:
        fields["throughput_criterion"] = "fail"
        fields["throughput_criterion_basis"] = (
            f"**서비스 회귀**: 호스트 부하는 낮은데(load1/코어 {load_ratio:.2f}) 벽시계가"
            f"{(1 - wall_ratio) * 100:.1f}% 줄었고 효율은 유지됐다 — 일이 줄어든 게 아니라 **대기가 늘었다**"
            f"(I/O·lock·fsync). {numbers}"
        )
    else:
        fields["throughput_criterion"] = "pass"
        fields["throughput_criterion_basis"] = f"벽시계·효율 모두 허용 안 — {numbers}"
    return fields


class _PhaseProfiler:
    """국면 하나씩 돌려 가며 **창 단위로 cProfile** 을 걸어 국면 내부의 함수별 시간을 모은다.

    설계상 중요한 세 가지:
      ① **창 하나 = 국면 하나.** 국면을 돌려 가며 계측하므로 “그 국면 안의 함수 순위”가 나온다.
      ② 계측 중인 반복은 호출자가 **판정 계열에서 제외**한다(`take()` 가 `None` 이 아닌 반복은 계열에 안 들어간다).
         계측이 판정을 오염시키면 “느려졌다”가 측정기 때문일 수 있다(§28 의 교훈).
      ③ 창의 **CPU 시간을 따로 잰다** — 프로파일러 오버헤드를 숨기지 않고 비율로 보고한다.
    """

    def __init__(self, phases: tuple[str, ...]) -> None:
        self.phases = phases
        self.enabled = DEEP_PROFILE_ENABLED
        self.windows: list[dict[str, Any]] = []
        # `callers` 는 **네 번째 칸**의 자료다: {함수 키: {호출자 키: 호출 수}} — cProfile 이 이미 들고 있는
        # 호출자 표를 창이 닫힐 때마다 옮겨 담는다(추가 계측 비용 0).
        self.per_phase: dict[str, dict[str, Any]] = {
            name: {"total_s": 0.0, "ops": 0, "windows": 0, "functions": {}, "callers": {}} for name in phases
        }
        self.profiled_calls = 0
        self._profiler = cProfile.Profile()
        self._phase: str | None = None
        self._calls_left = 0
        self._cpu_s = 0.0
        self._call_t0 = 0.0
        self._window_ops = 0

    def take(self, index: int) -> str | None:
        """이번 반복에 계측할 국면 이름을 돌려준다(`None` 이면 평소처럼 계열에 넣는다).

        주의: 국면 호출 수와 반복 수는 다르다(전이는 반복당 2회). 창 크기와 계수는 **호출 수**로 하고,
        단가는 반복 수로 나누므로 어느 국면이든 “µs/반복”으로 같게 맞는다.
        """
        if not self.enabled or self.profiled_calls >= DEEP_MAX_OPS:
            return None
        if self._calls_left <= 0:
            if len(self.windows) >= DEEP_MAX_WINDOWS or index % max(DEEP_SAMPLE_EVERY, 1) != 0:
                return None
            self._phase = self.phases[len(self.windows) % len(self.phases)]  # 국면을 돌려 가며
            self._calls_left = DEEP_WINDOW_CALLS
            self._cpu_s = 0.0
            self._window_ops = 0
        self._window_ops += 1  # 이 반복을 창에 포함(단가의 분모)
        return self._phase

    def active_for(self, phase: str) -> bool:
        """이 국면이 **지금** 창 안에 있는가.

        필요한 이유(프로브가 실측으로 잡은 결함): 전이는 반복당 2회 부르므로 창이 그 반복의 **첫 호출**에서
        닫힐 수 있다. 그때 같은 반복의 둘째 호출까지 계측하면 창이 **두 번 닫혀** 유령 창이 생기고(창 수가
        부풀고 국면 회전이 어긍나 세 번째 국면이 영영 안 돌아간다). 그래서 창이 닫힌 뒤의 꼬리 호출은
        계측하지 않는다.
        """
        return self._calls_left > 0 and self._phase == phase

    def enable(self) -> None:
        if self._calls_left <= 0:
            return
        self._call_t0 = time.process_time()
        self._profiler.enable()

    def disable(self) -> None:
        """국면 호출 **하나**의 CPU 를 더하고, 창이 다 차면 통계를 누적해 닫는다.

        첫 구현은 창 시작 시각에서 누적해 **호출마다 창 전체 시간을 다시 더했다**(전이는 반복당 2회라
        두 배로 부풀었다) — 프로브가 실측으로 잡았고, 지금은 호출 경계 사이의 델타만 더한다.
        """
        if self._calls_left <= 0:  # 창이 이미 닫렸다 — 꼬리 호출은 버린다(유령 창 금지)
            return
        self._profiler.disable()
        self._cpu_s += time.process_time() - self._call_t0
        self.profiled_calls += 1
        self._calls_left -= 1
        if self._calls_left > 0:
            return
        bucket = self.per_phase[self._phase or ""]
        bucket["total_s"] += self._cpu_s
        bucket["ops"] += self._window_ops
        bucket["windows"] += 1
        # 호출자 표까지 담긴 표를 얻는다(자세한 이유·주의는 `_pstats_table` 참조).
        for label, (cc, nc, tt, ct, callers) in _pstats_table(self._profiler).items():
            key, filename, line = _frame_key(label)
            slot = bucket["functions"].setdefault(
                key, {"self_s": 0.0, "cum_s": 0.0, "calls": 0, "file": filename, "line": line}
            )
            # pstats 튜플 순서(실측): `(cc, nc, tt, ct, callers)` — 자기 시간은 **tt**, 하위 포함은 **ct**.
            # (raw getstats 는 `(code, nc, cc, ns, tt, ct)` 로 **순서가 다르다** — 그 차이가 예전에 자기 시간과
            #  총합을 바꿔 읽은 원인이었다.)
            slot["self_s"] += float(tt)  # 자기 시간 — 순위의 근거
            slot["cum_s"] += float(ct)  # 하위 호출 포함 — 직관용
            slot["calls"] += int(nc)
            # 호출자 표: pstats 의 caller 값도 `(nc, cc, tt, ct)` 이므로 **0번이 호출 수**다.
            by_caller = bucket["callers"].setdefault(key, {})
            for caller_label, caller_stats in (callers or {}).items():
                caller_key, _cfile, _cline = _frame_key(caller_label)
                by_caller[caller_key] = by_caller.get(caller_key, 0) + int(caller_stats[0])
        self.windows.append(
            {
                "phase": self._phase,
                "ops": self._window_ops,
                "calls": DEEP_WINDOW_CALLS,
                "cpu_s": round(self._cpu_s, 4),
            }
        )
        self._profiler = cProfile.Profile()  # 창마다 새 프로파일러(누적이 겹치지 않게)

    def report(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "profiled_calls": self.profiled_calls,
            "windows": len(self.windows),
            "sample_every": DEEP_SAMPLE_EVERY,
            "window_calls": DEEP_WINDOW_CALLS,
            "max_windows": DEEP_MAX_WINDOWS,
            "max_ops": DEEP_MAX_OPS,
            "phases": {
                name: {
                    "total_s": round(bucket["total_s"], 4),
                    "ops": bucket["ops"],
                    "windows": bucket["windows"],
                    # 호출자 표(네 번째 칸의 입력) — 함수마다 상위 `PATH_TOP_CALLERS` 만 싣는다.
                    # 트리밍을 **리포트에서** 하는 이유: 네 번째 칸은 리포트만 보고 재현할 수 있어야 하므로,
                    # 읽는 쪽과 계산하는 쪽이 **같은 자료**를 봐야 한다.
                    "callers": {
                        key: dict(sorted(value.items(), key=lambda kv: (-kv[1], kv[0]))[:PATH_TOP_CALLERS])
                        for key, value in (bucket.get("callers") or {}).items()
                        if value
                    },
                    "functions": {
                        key: {
                            "self_s": round(value["self_s"], 6),
                            "cum_s": round(value["cum_s"], 6),
                            "calls": value["calls"],
                            "file": value["file"],
                            "line": value["line"],
                        }
                        for key, value in bucket["functions"].items()
                    },
                }
                for name, bucket in self.per_phase.items()
            },
        }


def phase_function_attribution(
    phase: str | None,
    profile: dict[str, Any],
    ladder_verdict: dict[str, Any],
    actual_duration_s: float,
) -> dict[str, Any]:
    """사다리의 **다음 칸**: 지목된 국면 **안**의 하위 단계를 함수별로 좁힌다(순수 함수).

    입력은 하네스가 창 단위로 모은 cProfile 통계다(국면별 total/ops/windows/functions).
    국면 경계 타이머가 답하지 못하는 질문에 답한다: `conversation.append` 안에서 **저널 한 줄 쓰기·
    view 재작성·tail 중 무엇**이 늘었나.

    산출 판정(`deep_criterion`):
      · `not_applicable` — 앞칸이 국면을 지목하지 않았거나 짧은 실행이거나 계측을 껐다(돌릴 이유가 없다)
      · `insufficient`  — 창이 너무 적거나 통계가 비었다(지목하지 않는다)
      · `function`      — 한 함수가 국면 안 시간의 `DEEP_FUNCTION_DOMINANCE` 이상
      · `spread_within_phase` — 여러 함수에 퍼졌다(그 국면 안에서 더 쪼갤 근거가 없다)
      · `outside_functions`   — 파이썬 밖(C 확장·커널 fsync) 잔차가 절반 초과 → “프로파일러가 못 보는 곳”

    **정직성 장치**: 계측 오버헤드 비율(`deep_overhead_ratio`)과 잔차(`deep_residual_*`)를 항상 싣고,
    계측한 창의 반복은 앞칸의 판정 계열에서 이미 제외되어 있다(`deep_profiled_calls` 로 밝힌다).
    """
    fields: dict[str, Any] = {
        "deep_criterion": "not_applicable",
        "deep_phase": phase,
        "deep_function": None,
        "deep_function_share": 0.0,
        "deep_functions_top": [],
        "deep_excluded_functions": 0,
        "deep_profiled_calls": int(profile.get("profiled_calls") or 0),
        "deep_windows": int(profile.get("windows") or 0),
        "deep_sample_every": DEEP_SAMPLE_EVERY,
        "deep_window_calls": DEEP_WINDOW_CALLS,
        "deep_max_windows": DEEP_MAX_WINDOWS,
        "deep_max_ops": DEEP_MAX_OPS,
        "deep_function_dominance": DEEP_FUNCTION_DOMINANCE,
        "deep_outside_ratio": DEEP_OUTSIDE_RATIO,
    }
    if ladder_verdict.get("attribution_criterion") != "phase":
        fields["deep_criterion_basis"] = (
            "하위 단계 귀속 불필요: 앞칸이 국면을 지목하지 않았다"
            f"(판정 `{ladder_verdict.get('attribution_criterion')}`) — 함수 순위는 지목된 국면에만 묻는다"
        )
        fields["deep_next_step"] = "없음(국면 미지목)"
        return fields
    if actual_duration_s < THROUGHPUT_MIN_RUN_S:
        fields["deep_criterion_basis"] = (
            f"하위 단계 귀속 불가: 실측 {actual_duration_s:.0f}s < 최소 {THROUGHPUT_MIN_RUN_S:.0f}s"
        )
        fields["deep_next_step"] = "8시간 규모에서 다시 잰다"
        return fields
    if not profile.get("enabled"):
        fields["deep_criterion_basis"] = (
            "하위 단계 귀속 불가: 창 계측이 꺼져 있다(`NX10_DEEP_PROFILE=0`) — 이 칸은 **설명용**이라"
            " 꺼도 통과/실패 판정은 약해지지 않지만, 왜 느린지는 말할 수 없다"
        )
        fields["deep_next_step"] = "재실행(계측을 켜고) — 판정은 그대로 유효하다"
        return fields
    bucket = (profile.get("phases") or {}).get(phase or "") or {}
    ops = int(bucket.get("ops") or 0)
    if int(bucket.get("windows") or 0) < DEEP_MIN_WINDOWS or ops <= 0:
        fields["deep_criterion"] = "insufficient"
        fields["deep_criterion_basis"] = (
            f"하위 단계 귀속 불가: 국면 `{phase}` 의 창이 {int(bucket.get('windows') or 0)}개"
            f"(최소 {DEEP_MIN_WINDOWS}개 필요) · 계측 반복 {ops} — 표본이 너무 적다"
        )
        fields["deep_next_step"] = f"`NX10_DEEP_SAMPLE_EVERY` 를 낮추거나 실행을 늘린다(현재 {DEEP_SAMPLE_EVERY})"
        return fields
    total_us_per_op = round(float(bucket["total_s"]) / ops * 1e6, 3)
    rows: list[tuple[str, float, float, int]] = []
    instrument_us_per_op = 0.0
    excluded = 0
    for key, value in (bucket.get("functions") or {}).items():
        # 계측기 자신(하네스 파일)의 프레임은 **순위에서 뺀다** — 안 빼면 사다리가 자기 자신을 지목한다.
        # 뺀 몫은 버리지 않고 `deep_instrument_us_per_op` 로 밝혀서, 잔차 계산에서도 떼어 낸다.
        # 판정은 **키 규칙**으로 한다(리포트만 보고도 같은 판정이 나와야 하므로 — `file` 필드에
        # 매달리면 파일을 옮긴 뒤 경로가 달라질 때 조용히 달라진다).
        if _is_instrument_frame(str(key)):
            instrument_us_per_op += float(value["self_s"]) / ops * 1e6
            excluded += 1
            continue
        rows.append(
            (
                key,
                round(float(value["self_s"]) / ops * 1e6, 3),
                round(float(value["cum_s"]) / ops * 1e6, 3),
                int(value["calls"]),
            )
        )
    rows.sort(key=lambda row: -row[1])
    top_name, top_self = (rows[0][0], rows[0][1]) if rows else (None, 0.0)
    share = round(top_self / total_us_per_op, 4) if total_us_per_op > 0 else 0.0
    units = (ladder_verdict.get("attribution_units_us_per_op") or {}).get(phase or "")
    phase_unit_last = float(units[1]) if isinstance(units, list) and len(units) == 2 else 0.0
    instrument_us_per_op = round(instrument_us_per_op, 3)
    product_us_per_op = round(total_us_per_op - instrument_us_per_op, 3)
    # 잔차 = 국면 단가 − **파이썬이 본 제품 몫**(계측기 몫을 뺀 뒤). 남는 것이 프로파일러가 못 보는 몫이다.
    residual = round(phase_unit_last - product_us_per_op, 3)
    residual_ratio = round(residual / phase_unit_last, 4) if phase_unit_last > 0 else 0.0
    overhead = round(total_us_per_op / phase_unit_last, 4) if phase_unit_last > 0 else -1.0
    fields.update(
        {
            "deep_total_us_per_op": total_us_per_op,
            "deep_instrument_us_per_op": instrument_us_per_op,
            "deep_product_us_per_op": product_us_per_op,
            "deep_excluded_functions": excluded,
            "deep_phase_unit_us_per_op": phase_unit_last,
            "deep_residual_us_per_op": residual,
            "deep_residual_ratio": residual_ratio,
            "deep_overhead_ratio": overhead,
            "deep_function": top_name,
            "deep_function_share": share,
            "deep_functions_top": [
                {"function": key, "self_us_per_op": self_us, "cum_us_per_op": cum_us, "calls": calls}
                for key, self_us, cum_us, calls in rows[:DEEP_TOP_FUNCTIONS]
            ],
        }
    )
    numbers = (
        f"국면 `{phase}` 단가 {phase_unit_last:.1f} µs/반복 · 계측 반복 {ops}(창 {int(bucket['windows'])}개)"
        f" · 파이썬이 본 몫 {product_us_per_op:.1f} µs/반복(계측기 {instrument_us_per_op:.1f} 는 제외)"
        f" · 프로파일러가 못 본 잔차 {residual:+.1f}({residual_ratio * 100:.0f}%)"
    )
    if residual < 0:
        # 음수 잔차 = 프로파일러 오버헤드가 국면 시간을 부풀린 것. 이걸 숨기면 “파이썬 밖은 없다”를
        # “파이썬 밖이 마이너스”로 말하게 된다 — 실측(프로브)에서 오버헤드 비율 1.50 으로 실제로 나왔다.
        fields["deep_residual_note"] = (
            f"계측 오버헤드가 국면 시간을 {overhead:.2f}배로 부풀렸다(잔차가 음수) —"
            " 이 실행의 “파이썬 밖 몫”은 0 으로 읽고, 함수 순위만 쓴다(다음 8시간 실행은 이 칸 없이 잰다)"
        )
    if residual_ratio > DEEP_OUTSIDE_RATIO and residual > 0:
        fields["deep_criterion"] = "outside_functions"
        fields["deep_criterion_basis"] = (
            f"파이썬 밖에 있다: 국면 시간의 {residual_ratio * 100:.0f}% 가 프로파일러에 안 보인다"
            f"(C 확장 sqlite·json 인코더나 커널 fsync) — {numbers}"
        )
        fields["deep_next_step"] = (
            "프로파일러가 못 보는 곳을 본다: 그 국면의 syscall·바이트 수(쓰기량·fsync 횟수)를 재거나"
            " py-spy 같은 C 스택까지 보는 도구를 쓴다"
        )
    elif top_name is not None and share >= DEEP_FUNCTION_DOMINANCE:
        fields["deep_criterion"] = "function"
        fields["deep_criterion_basis"] = (
            f"그 함수다: **{top_name}** 이 국면 안 파이썬 시간의 {share * 100:.0f}%"
            f"(자기 시간 {top_self:.1f} µs/반복) — {numbers}"
        )
        fields["deep_next_step"] = f"`{top_name}` 을 본다: 그 파일의 호출 경로와 하위 호출을 짚는다"
    else:
        fields["deep_criterion"] = "spread_within_phase"
        fields["deep_criterion_basis"] = (
            f"국면 안에 퍼졌다: 한 함수가 지배하지 않는다(최대 {top_name or '없음'} {share * 100:.0f}%) — {numbers}"
        )
        fields["deep_next_step"] = (
            "그 국면 자체를 줄이는 방향(일감량·구조)을 본다 — 함수 하나를 범인으로 만들 근거가 없다"
        )
    return fields


def _caller_chain(callers_map: dict[str, dict[str, int]], start: str) -> tuple[list[str], int]:
    """지목된 함수에서 **위로** 지배 호출자를 따라 올라간다(`PATH_MAX_DEPTH` 칸까지).

    계측기 프레임(하네스 파일·`_lsprof` 가짜 프레임)은 경로에서 **건너뛴다** — 계측 wrapper 는 제품의
    호출 경로가 아니기 때문이다. 건너뛴 수를 함께 돌려주어 “경로가 거기서 끝났다”와 “계측기를 지나
    더 올라갈 곳이 없다”를 구분할 수 있게 한다.
    """
    chain: list[str] = []
    skipped = 0
    current = start
    for _ in range(PATH_MAX_DEPTH):
        candidates = callers_map.get(current) or {}
        ranked = sorted(
            ((key, int(value)) for key, value in candidates.items() if not _is_instrument_frame(key)),
            key=lambda kv: (-kv[1], kv[0]),
        )
        skipped += sum(1 for key in candidates if _is_instrument_frame(key))
        if not ranked:
            break
        chain.append(ranked[0][0])
        current = ranked[0][0]
    return chain, skipped


def function_call_path(
    deep_verdict: dict[str, Any],
    profile: dict[str, Any],
    actual_duration_s: float,
) -> dict[str, Any]:
    """사다리의 **네 번째 칸**: 지목된 함수를 **어느 경로가** 부르고 **반복당 몇 번** 부르는가(순수 함수).

    앞칸(`phase_function_attribution`)이 “`posix.fsync` 다”까지 말한 뒤에 남는 두 질문에 답한다:
      · **누가** 부르는가 — cProfile 이 들고 있는 호출자 표(`profile[...]["callers"]`)
      · **얼마나 자주** 부르는가 — 호출 수 ÷ 계측 반복 수

    둘을 나눠 내는 이유는 **처방이 다르기 때문**이다: 반복당 1회면 그 호출 자체를 싸게 만들어야 하고
    (정책·배치·비동기화), 반복당 여러 번이면 **호출을 합쳐야** 한다(코얼레싱). 같은 함수·같은 시간이라도
    다른 수술이고, 이 칸이 그것을 문장으로 가른다(`path_frequency_class` · `path_frequency_note`).

    산출 판정(`path_criterion`):
      · `not_applicable` — 앞칸이 함수를 지목하지 않았거나 짧은/계측 꺼짐 실행(돌릴 이유가 없다)
      · `insufficient`  — 창이 적거나 호출자 표가 비었거나 기록이 불완전하다(지목하지 않는다)
      · `path`          — 한 호출자가 그 함수 호출의 `PATH_MIN_CALLER_SHARE` 이상
      · `multi_path`    — 여러 곳이 부르고 지배자가 없다 → 공통 함수 **자체**를 싸게 만드는 방향

    호출 수의 분모는 그 함수 자신의 호출 수(`calls`)다 — 보관한 상위 호출자만 더한 값이 아니다(트리밍된
    호출자가 있는데 몫을 부풀리면 “지배자”를 지어내게 된다).

    **하네스가 직접 부르는 경우를 숨기지 않는다**: 국면 진입점 함수(예: `create_task`)는 호출자가 하네스
    루프다. 그것을 “계측기라서 제외”하면 아무 호출자도 없는 것처럼 보이지만, 사실은 **제품 쪽 호출 경로가
    없다**는 뜻이고 처방도 그에 맞다(그 함수 자체를 싸게). 그래서 하네스 프레임은 순위에서 빼는 대신
    `path_caller_is_instrument` 로 **밝히고** 처방을 바꾼다.
    """
    fields: dict[str, Any] = {
        "path_criterion": "not_applicable",
        "path_phase": deep_verdict.get("deep_phase"),
        "path_function": None,
        "path_calls": 0,
        "path_calls_per_iteration": 0.0,
        "path_frequency_class": "unknown",
        "path_frequency_note": "",
        "path_caller": None,
        "path_caller_is_instrument": False,
        "path_caller_share": 0.0,
        "path_callers_top": [],
        "path_chain": [],
        "path_instrument_frames_skipped": 0,
        "path_min_caller_share": PATH_MIN_CALLER_SHARE,
        "path_top_callers": PATH_TOP_CALLERS,
        "path_max_depth": PATH_MAX_DEPTH,
        "path_repeat_per_iteration": PATH_REPEAT_PER_ITERATION,
    }
    if deep_verdict.get("deep_criterion") != "function":
        fields["path_criterion_basis"] = (
            "호출 경로 귀속 불필요: 앞칸이 함수를 지목하지 않았다"
            f"(판정 `{deep_verdict.get('deep_criterion')}`) — 경로는 지목된 함수에만 묻는다"
        )
        fields["path_next_step"] = "없음(함수 미지목)"
        return fields
    fields["path_function"] = deep_verdict.get("deep_function")
    if actual_duration_s < THROUGHPUT_MIN_RUN_S:
        fields["path_criterion_basis"] = (
            f"호출 경로 귀속 불가: 실측 {actual_duration_s:.0f}s < 최소 {THROUGHPUT_MIN_RUN_S:.0f}s"
        )
        fields["path_next_step"] = "8시간 규모에서 다시 잰다"
        return fields
    if not profile.get("enabled"):
        fields["path_criterion_basis"] = (
            "호출 경로 귀속 불가: 창 계측이 꺼져 있다(`NX10_DEEP_PROFILE=0`) — 앞칸과 같은 이유로"
            " “왜 느린지 말할 수 없다”만 남는다"
        )
        fields["path_next_step"] = "재실행(계측을 켜고) — 판정은 그대로 유효하다"
        return fields
    phase = deep_verdict.get("deep_phase")
    function = str(deep_verdict.get("deep_function") or "")
    bucket = (profile.get("phases") or {}).get(phase or "") or {}
    ops = int(bucket.get("ops") or 0)
    calls = int(((bucket.get("functions") or {}).get(function) or {}).get("calls") or 0)
    callers = (bucket.get("callers") or {}).get(function) or {}
    ranked = sorted(((key, int(value)) for key, value in callers.items()), key=lambda kv: (-kv[1], kv[0]))
    if int(bucket.get("windows") or 0) < DEEP_MIN_WINDOWS or ops <= 0 or calls <= 0 or not ranked:
        fields["path_criterion"] = "insufficient"
        fields["path_criterion_basis"] = (
            f"호출 경로 귀속 불가: 국면 `{phase}` 창 {int(bucket.get('windows') or 0)}개 · 계측 반복 {ops}"
            f" · `{function}` 호출 {calls} · 기록된 호출자 {len(ranked)}곳"
            " — 호출자를 말할 표본이 없다(창이 모자라거나 C 쪽에서만 불린다)"
        )
        fields["path_next_step"] = (
            f"`NX10_DEEP_SAMPLE_EVERY` 를 낮추거나 실행을 늘린다(현재 {DEEP_SAMPLE_EVERY})"
            " · 호출자가 C 쪽이면 이 칸은 답하지 못한다(다음은 syscall·trace 도구)"
        )
        return fields
    calls_per_iteration = round(calls / ops, 3)
    if calls_per_iteration >= PATH_REPEAT_PER_ITERATION:
        fields["path_frequency_class"] = "repeated_per_iteration"
        fields["path_frequency_note"] = (
            f"반복당 {calls_per_iteration:.2f}회 — **호출을 합치는** 쪽이 처방이다: 한 반복에 여러 번 부른다는"
            " 것은 한 번으로 줄일 여지가 있다는 뜻이다(중복 제거·일괄 처리)"
        )
    else:
        fields["path_frequency_class"] = "at_most_once_per_iteration"
        fields["path_frequency_note"] = (
            f"반복당 {calls_per_iteration:.2f}회 — 횟수가 아니라 **그 호출 자체의 비용**이 문제다"
            "(정책·배치·비동기화로 비용을 낮춘다)"
        )
    top_caller, top_calls = ranked[0]
    share = round(top_calls / calls, 4)
    chain, skipped = _caller_chain(bucket.get("callers") or {}, function)
    fields.update(
        {
            "path_calls": calls,
            "path_calls_per_iteration": calls_per_iteration,
            "path_caller": top_caller,
            "path_caller_share": share,
            "path_callers_top": [
                {
                    "caller": key,
                    "calls": value,
                    "calls_per_iteration": round(value / ops, 3),
                    "share": round(value / calls, 4),
                }
                for key, value in ranked[:PATH_TOP_CALLERS]
            ],
            "path_chain": chain,
            "path_instrument_frames_skipped": skipped,
        }
    )
    numbers = (
        f"`{function}` 이 국면 `{phase}` 에서 반복당 {calls_per_iteration:.2f}회 불린다"
        f"(창 {int(bucket['windows'])}개 · 계측 반복 {ops} · 기록된 호출자 {len(ranked)}곳)"
        f" · 경로: {' ← '.join([function, *chain])}"
    )
    fields["path_caller_is_instrument"] = _is_instrument_frame(top_caller)
    if share >= PATH_MIN_CALLER_SHARE:
        fields["path_criterion"] = "path"
        if fields["path_caller_is_instrument"]:
            # 국면 진입점: 호출자가 하네스(계측기)다 = **제품 쪽 호출 경로가 없다**는 뜻(처방이 달라진다).
            fields["path_criterion_basis"] = (
                f"국면 진입점이다: `{function}` 을 **하네스가 직접** 부른다"
                f"({share * 100:.0f}% · 호출 {top_calls}회) — 제품 쪽 호출 경로가 없다. {numbers}"
            )
            fields["path_next_step"] = (
                "부르는 곳을 고칠 것이 없다 — **그 함수 자체**를 싸게 만든다: " + fields["path_frequency_note"]
            )
        else:
            fields["path_criterion_basis"] = (
                f"그 경로다: **{top_caller}** 가 `{function}` 호출의 {share * 100:.0f}%(호출 {top_calls}회) — {numbers}"
            )
            fields["path_next_step"] = f"`{top_caller}` 경로를 본다 — {fields['path_frequency_note']}"
    elif len(ranked) >= 2:
        fields["path_criterion"] = "multi_path"
        heads = " · ".join(f"{key} {value / calls * 100:.0f}%" for key, value in ranked[:3])
        fields["path_criterion_basis"] = f"여러 경로가 같은 함수를 부른다: 한 곳이 지배하지 않는다({heads}) — {numbers}"
        fields["path_next_step"] = (
            "부르는 곳을 고치는 대신 **그 함수 자체**를 싸게 만드는 방향 — " + fields["path_frequency_note"]
        )
    else:
        # 한 곳만 기록됐는데 그 몫이 절반 미만이다 = 호출자 표가 불완전하다(재귀·C 프레임 등).
        # 이때 그 한 곳을 “범인”이라 부르면 트리밍된 나머지를 숨기는 것이므로 지목하지 않는다.
        fields["path_criterion"] = "insufficient"
        fields["path_criterion_basis"] = (
            f"호출자 표가 불완전하다: 기록된 곳이 `{top_caller}` 하나인데 그 몫이 {share * 100:.0f}%"
            f"(절반 미만) — 나머지 호출의 출처를 모른다. {numbers}"
        )
        fields["path_next_step"] = "호출자 표가 더 필요하다(창을 늘리거나 trace 도구로 본다)"
    return fields


def throughput_attribution(
    phases: tuple[str, ...],
    phase_cpu_s: list[list[float]],
    attribution_ops: list[int],
    attribution_times_s: list[float],
    sample_ops: list[int],
    sample_times_s: list[float],
    sample_cpu_s: list[float],
    throughput_verdict: dict[str, Any],
    actual_duration_s: float,
) -> dict[str, Any]:
    """처리량 회귀가 **빨간일 때만** 돌아 “어느 국면이 느려졌나”를 좁히는 **귀속 사다리**(순수 함수).

    입력은 하네스가 국면마다 적립한 누적 CPU 초와 누적 반복 수(`SOAK_PHASES` 순서) **그리고** 같은 실행의
    전체 CPU 표본이다. 둘을 함께 받는 이유가 핵심이다: 국면 타이머는 **경계 안**만 보고, 루프 자체·표본
    수집·할당자·GC 는 어느 국면에도 안 붙는다. 그래서 총량은 전체 표본에서 재고 국면 합은 국면에서 재서
    **차이를 잔차로 남긴다** — 잔차가 크면 “국면 밖”이라고 말한다(국면 합을 총량으로 쓰면 잔차가
    정의상 0 이 되어 그 판정이 영영 안 난다).
    국면 단가는 같은 블록 추정량(블록 = `max(5분, 지속×2%)` 중앙값 · 워밍업 창 제외 · 분기 1/4)으로 재고,
    분기 사이 증가분(µs/반복)을 국면별로 쪼갠다. 쪼갠 합이 총 증가분과 같아야 하므로(정체식) **잔차**를 남긴다.

    산출 판정(`attribution_criterion`):
      · `not_applicable` — 게이트가 빨갭지 않거나 실행이 짧다(돌릴 이유가 없다. 사다리는 설명이지 판정이 아니다)
      · `phase`          — 한 국면이 증가분의 `ATTRIBUTION_DOMINANCE` 이상(그 이름과 몫을 낸다)
      · `spread`         — 증가가 국면들에 퍼졌고 합이 총량을 설명한다(잔차 작음)
      · `outside_phases` — 계측 밖 비중이 크다(할당자·GC·인터프리터 · 잔차가 절반 초과)
      · `insufficient`   — 게이트는 빨간데 이 실행의 총 증가가 잡음 수준(범인을 만들지 않는다)

    리포트만으로 같은 쪼개기를 재현할 수 있도록 국면 단가·증가분·잔차를 모두 싣는다.
    """
    fields: dict[str, Any] = {
        "attribution_phases": list(phases),
        "attribution_dominance": ATTRIBUTION_DOMINANCE,
        "attribution_min_delta_ratio": ATTRIBUTION_MIN_DELTA_RATIO,
        "attribution_sample_every": ATTRIBUTION_SAMPLE_EVERY,
        "attribution_units_us_per_op": {},
        "attribution_contributions_us_per_op": {},
        "attribution_speedups_us_per_op": {},
        "attribution_samples": len(attribution_ops),
    }
    if throughput_verdict.get("throughput_criterion") != "fail":
        fields["attribution_criterion"] = "not_applicable"
        fields["attribution_criterion_basis"] = (
            "귀속 불필요: 처리량 게이트가 빨간색이 아니다"
            f"(판정 `{throughput_verdict.get('throughput_criterion')}`) — 사다리는 빨간 실행에서만 돈다"
        )
        fields["attribution_next_step"] = "없음(게이트 초록)"
        return fields
    if actual_duration_s < THROUGHPUT_MIN_RUN_S:
        fields["attribution_criterion"] = "not_applicable"
        fields["attribution_criterion_basis"] = (
            f"귀속 불가: 실측 {actual_duration_s:.0f}s < 최소 {THROUGHPUT_MIN_RUN_S:.0f}s —"
            " 분기 단가를 잴 수 없는 실행에서는 국면을 지목하지 않는다"
        )
        fields["attribution_next_step"] = "8시간 규모에서 다시 잰다"
        return fields
    block_s = max(THROUGHPUT_BLOCK_MIN_S, actual_duration_s * THROUGHPUT_BLOCK_FRACTION)
    window_s = sc6_warmup_window_s(actual_duration_s)
    fields["attribution_block_s"] = round(block_s, 1)
    fields["attribution_warmup_window_s"] = round(window_s, 1)
    series = [list(values) for values in phase_cpu_s]
    if len(series) != len(phases) or len(attribution_ops) < 4 or len(attribution_times_s) != len(attribution_ops):
        fields["attribution_criterion"] = "insufficient"
        fields["attribution_criterion_basis"] = "국면별 계열이 비었거나 길이가 맞지 않는다 — 귀속할 재료가 없다"
        fields["attribution_next_step"] = "하네스가 국면 CPU 를 적립하는지 확인한다"
        return fields
    for values in series:
        if len(values) != len(attribution_ops):
            fields["attribution_criterion"] = "insufficient"
            fields["attribution_criterion_basis"] = "국면 하나의 표본 수가 맞지 않는다 — 어느 국면에 귀속할지 판단 불가"
            fields["attribution_next_step"] = "하네스가 모든 국면을 같은 시점에 스냅샷하는지 확인한다"
            return fields  # 국면별 **블록 단가**(µs/반복)와 **전체** 블록 단가 — 블록 버킷은 처리량 게이트와 같은 기준(시각//블록).
    buckets: dict[int, list[list[float]]] = {}
    for index in range(1, len(attribution_ops)):
        start = attribution_times_s[index - 1]
        span = attribution_times_s[index] - start
        delta_ops = attribution_ops[index] - attribution_ops[index - 1]
        if span <= 0 or delta_ops <= 0 or start < window_s or attribution_times_s[index] < window_s:
            continue
        units = []
        for values in series:
            delta_cpu = values[index] - values[index - 1]
            if delta_cpu < 0:
                break
            units.append(delta_cpu / delta_ops * 1e6)
        else:
            buckets.setdefault(int(attribution_times_s[index] // block_s), []).append(units)
    # 전체 단가는 **프로세스 전체 CPU 표본**에서 잰다(국면 합이 아니다 — 잔차가 정의상 0 이 되면
    # “국면 밖”이라는 판정이 영영 안 난다). 같은 블록 키로 모아 국면과 같은 분기에 짝지운다.
    total_buckets: dict[int, list[float]] = {}
    if len(sample_ops) == len(sample_times_s) == len(sample_cpu_s):
        for index in range(1, len(sample_ops)):
            start = sample_times_s[index - 1]
            span = sample_times_s[index] - start
            delta_ops = sample_ops[index] - sample_ops[index - 1]
            delta_cpu = sample_cpu_s[index] - sample_cpu_s[index - 1]
            if span <= 0 or delta_ops <= 0 or delta_cpu <= 0:
                continue
            if start < window_s or sample_times_s[index] < window_s:
                continue
            total_buckets.setdefault(int(sample_times_s[index] // block_s), []).append(delta_cpu / delta_ops * 1e6)
    keys = sorted(set(buckets) & set(total_buckets))
    quarter = max(THROUGHPUT_MIN_BLOCKS_PER_QUARTER, len(keys) // 4)
    fields["attribution_blocks"] = len(keys)
    if len(keys) < quarter * 2:
        fields["attribution_criterion"] = "insufficient"
        fields["attribution_criterion_basis"] = (
            f"귀속 불가: 창 밖에서 국면 · 전체 표본이 겹치는 블록이 {len(keys)}개"
            f"(블록 {block_s:.0f}s · 분기마다 {quarter}개 필요) — 두 계열의 스냅샷 간격"
            f"(국면 {ATTRIBUTION_SAMPLE_EVERY} 반복 · 전체 50 반복)을 좁히거나 실행을 늘려야 한다"
        )
        fields["attribution_next_step"] = (
            f"`NX10_ATTRIBUTION_SAMPLE_EVERY` 를 낮추거나(현재 {ATTRIBUTION_SAMPLE_EVERY}) 더 긴 실행으로 다시 잰다"
        )
        return fields
    # 분기 안의 **모든 구간 행**을 펼친 뒤 국면별 중간값을 낸다(버킷 단위로 중간값을 내면 블록이 두 번 접힌다).
    first_rows = [row for key in keys[:quarter] for row in buckets[key]]
    last_rows = [row for key in keys[-quarter:] for row in buckets[key]]
    totals_first = [_median(total_buckets[key]) for key in keys[:quarter]]
    totals_last = [_median(total_buckets[key]) for key in keys[-quarter:]]
    units_first = [round(_median([row[i] for row in first_rows]), 3) for i in range(len(phases))]
    units_last = [round(_median([row[i] for row in last_rows]), 3) for i in range(len(phases))]
    contributions = {
        name: round(unit_last - unit_first, 3) for name, unit_first, unit_last in zip(phases, units_first, units_last)
    }
    total_first = round(_median(totals_first), 3)
    total_last = round(_median(totals_last), 3)
    total_delta = round(total_last - total_first, 3)
    attributed_delta = round(sum(contributions.values()), 3)
    gap = round(total_delta - attributed_delta, 3)
    positive = {name: value for name, value in contributions.items() if value > 0}
    speedups = {name: value for name, value in contributions.items() if value < 0}
    positive_total = round(sum(positive.values()), 3)
    top_name = max(positive, key=lambda name: positive[name]) if positive else None
    top_share = round(positive[top_name] / positive_total, 4) if top_name and positive_total > 0 else 0.0
    gap_ratio = round(abs(gap) / max(total_delta, 1e-9), 4) if total_delta > 0 else 0.0
    fields.update(
        {
            "attribution_units_us_per_op": {
                name: [unit_first, unit_last] for name, unit_first, unit_last in zip(phases, units_first, units_last)
            },
            "attribution_contributions_us_per_op": contributions,
            "attribution_speedups_us_per_op": speedups,
            "attribution_total_us_per_op": [total_first, total_last],
            "attribution_total_delta_us_per_op": total_delta,
            "attribution_attributed_delta_us_per_op": attributed_delta,
            "attribution_gap_us_per_op": gap,
            "attribution_gap_ratio": gap_ratio,
            "attribution_phase": top_name,
            "attribution_top_share": top_share,
            "attribution_gate_efficiency_ratio": throughput_verdict.get("throughput_efficiency_ratio"),
        }
    )
    numbers = (
        "단가 "
        + f"{total_first:.1f}→{total_last:.1f} µs/반복({(total_delta / max(total_first, 1e-9)) * 100:+.1f}%)"
        + " · 국면별 증가분 "
        + (
            " ".join(f"{name} {value:+.1f}" for name, value in sorted(contributions.items(), key=lambda item: -item[1]))
            or "없음"
        )
        + f" · 국면 밖 잔차 {gap:+.1f}({gap_ratio * 100:.0f}%)"
    )
    if total_delta < ATTRIBUTION_MIN_DELTA_RATIO * max(total_first, 1e-9):
        fields["attribution_criterion"] = "insufficient"
        fields["attribution_criterion_basis"] = (
            "귀속할 증가가 없다: 총 증가가 첫 분기 단가의 "
            f"{ATTRIBUTION_MIN_DELTA_RATIO * 100:.0f}% 미만이다(잡음 수준) — 없는 범인을 지목하지 않는다. {numbers}"
        )
        fields["attribution_next_step"] = "재실행(게이트가 효율 임계로 빨개졌지만 이 실행의 단가 증가는 잡음 수준)"
    elif gap_ratio > ATTRIBUTION_OUTSIDE_GAP_RATIO:
        fields["attribution_criterion"] = "outside_phases"
        fields["attribution_criterion_basis"] = (
            "계측 밖에 있다: 국면별 증가분을 다 더해도 총 증가와 맞지 않는다"
            f"(잔차 {gap:+.1f} µs/반복 = 총 증가의 {gap_ratio * 100:.0f}%) — 할당자·GC·인터프리터·루프 자체를 봐야 한다. {numbers}"
        )
        fields["attribution_next_step"] = (
            "그 프로세스 전체를 잡는다: 재실행에서 cProfile/py-spy 로 전체 콜 스택을 샘플링한다"
            "(국면 타이머는 경계만 보므로 경계 밖 비용은 여기서만 보인다)"
        )
    elif top_name is not None and top_share >= ATTRIBUTION_DOMINANCE:
        fields["attribution_criterion"] = "phase"
        fields["attribution_criterion_basis"] = (
            f"그 국면이다: **{top_name}** 이 증가분의 {top_share * 100:.0f}%"
            f"(+{positive[top_name]:.1f} µs/반복)를 차지한다 — {numbers}"
        )
        fields["attribution_next_step"] = (
            f"`{top_name}` 내부를 본다: 그 경로의 하위 단계(직렬화·fsync·lock)를 계약 시험이나 프로파일로 잡는다"
        )
    else:
        fields["attribution_criterion"] = "spread"
        spread_names = ", ".join(
            f"{name} {value:+.1f}" for name, value in sorted(positive.items(), key=lambda item: -item[1])
        )
        fields["attribution_criterion_basis"] = (
            f"고르게 늘었다: 한 국면이 지배하지 않는다(최대 {top_name or '없음'} {top_share * 100:.0f}%) — {spread_names}. {numbers}"
        )
        fields["attribution_next_step"] = (
            "공통 경로를 본다(모든 국면이 지나는 직렬화·할당·로그) — 국면 타이머로는 더 좁혀지지 않는다"
        )
    return fields


def criteria_gate(
    rss_verdict: dict[str, Any], throughput_verdict: dict[str, Any], actual_duration_s: float
) -> tuple[bool, str]:
    """두 축의 판정을 **시나리오 통과 여부**로 접고, 왜 그런지를 문장으로 돌려준다.

    왜 이 문이 필요한가(실측 2026-09-17, 스테이징본 점검): 종전 규칙은 `!= "fail"` 이어서 **8시간 실행이
    `not_applicable` 로 끝나도 통과**했다 — 즉 환경 변수 한 줄로 게이트를 비울 수 있었다(조용한 통과).
    반대로 `not_applicable` 을 무조건 실패로 만들면 60초 리허설이 영원히 빨간불이 되고, 그러면
    아무도 그 불을 안 본다. 그래서 **그 축의 최소 길이보다 짧을 때만** 면제한다:
      · RSS: 창(=`max(5분, 지속×5%)`)의 두 배 안에서는 “증가”를 말할 수 없다
      · 처리량: 2시간 미만에서는 시작 비용이 지배한다
    그보다 긴 실행에서 `not_applicable` 이면 **판정 불가를 통과로 취급하지 않는다**(재실행 요구).
    """
    unjudgeable: list[str] = []
    for label, verdict, key, floor in (
        ("RSS", rss_verdict, "rss_criterion", float(rss_verdict.get("rss_warmup_window_s") or 0) * 2),
        ("처리량", throughput_verdict, "throughput_criterion", THROUGHPUT_MIN_RUN_S),
    ):
        state = verdict.get(key)
        if state == "fail":
            return False, f"{label} 축 실패 — {verdict.get(key.replace('_criterion', '_criterion_basis'), '')}"
        if state == "not_applicable" and actual_duration_s >= floor:
            unjudgeable.append(f"{label}(최소 {floor:.0f}s 이상인데 판정 불가)")
    if unjudgeable:
        return False, (
            "판정 불가를 통과로 취급하지 않는다: " + " · ".join(unjudgeable) + " — 조건을 고쳐 다시 재야 한다"
        )
    return True, "두 축 모두 판정됨(실패 없음 — 짧은 실행의 판정 불가는 면제)"


def scenario_soak(workdir: Path, seconds: int) -> dict[str, Any]:
    from antigravity_k.engine.conversation_store import ConversationStore
    from antigravity_k.engine.task_state_store import TaskStateStore

    db_path = str(workdir / "soak.db")
    store = TaskStateStore(db_path)
    store.initialize()
    conv_store = ConversationStore(storage_dir=workdir / "soak-conversations")
    rss_samples: list[float] = []
    # SC-6 기준 재설계: 창 밖 증가와 반복당 creep 을 재려면 **표본의 시각·반복 수**가 필요하다.
    # 리포트에는 결과 인덱스·값만 싣고 이 두 목록은 메모리에만 둔다(리포트 크기를 늘리지 않는다).
    sample_times_s: list[float] = []
    sample_ops: list[int] = []
    # 처리량 회귀 축(2026-09-17): 벽시계 감소를 **효율 × 이용률** 로 분해하려면 표본마다 CPU 시간이 필요하고,
    # 그 감소가 경합 탓인지 가르려면 호스트 부하도 같이 남겨야 한다(둘 다 `ps`/`time` 수준이라 싸다).
    sample_cpu_s: list[float] = []
    sample_load1: list[float] = []
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
    # 귀속 사다리(2026-09-17): 국면 경계에서 CPU 시간을 적립한다(한 반복에 세 번). 반복 끝에서 시계를
    # **청구 없이** 리셋하므로 루프 자체와 표본 수집 비용은 어느 국면에도 안 들어가고, 그만큼이 자연히
    # “국면 밖 잔여”로 남는다(그 잔여가 크면 사다리는 “계측 밖”이라고 말한다 — 지어내지 않는다).
    phase_cpu = [0.0] * len(SOAK_PHASES)
    attribution_cpu_s: list[list[float]] = [[] for _ in SOAK_PHASES]
    attribution_ops: list[int] = []
    attribution_times_s: list[float] = []
    attribution_measured_ops = 0  # **계측된** 반복만 센다(창 계측분은 판정 계열에서 빠진다)
    _clock = [time.process_time()]
    profiler = _PhaseProfiler(SOAK_PHASES)
    _deep_phase: list[str | None] = [None]

    def _lap(index: int) -> None:
        now = time.process_time()
        if _deep_phase[0] == SOAK_PHASES[index]:
            # 창 계측 중인 국면은 **판정 계열에 안 넣는다**(계측이 판정을 오염시키지 않는다).
            _clock[0] = now
            return
        phase_cpu[index] += now - _clock[0]
        _clock[0] = now

    def _profiled(index: int, call: Callable[[], Any]) -> Any:
        """국면 호출을 창 계측과 함께 실행한다(계측 중이 아니면 그냥 부른다 — 비용은 함수 호출 하나).

        `_deep_phase`(이번 반복의 계측 국면)가 아니라 `active_for` 로 묻는다: 창이 이 반복의 첫 호출에서
        닫혔을 수 있으므로 “이 호출이 창 안인가”를 호출 시점에 다시 확인해야 한다(유령 창 방지).
        """
        phase = SOAK_PHASES[index]
        if not profiler.active_for(phase):
            return call()
        profiler.enable()
        try:
            return call()
        finally:
            profiler.disable()

    started = time.time()
    deadline = started + seconds
    i = 0
    while time.time() < deadline:
        tid = f"soak-{i}"
        _deep_phase[0] = profiler.take(i)  # 이번 반복에 계측할 국면(창 단위로 국면을 돌려 간다)
        try:
            _profiled(0, lambda: store.create_task(tid, "soak", "pending", "2026-09-09T00:00:00Z"))
            _lap(0)
            _profiled(1, lambda: store.transition(tid, "running", expected_status="pending"))
            _profiled(1, lambda: store.transition(tid, "done", output="ok", expected_status="running"))
            _lap(1)
            ops += 1
        except Exception:
            errors += 1
        # FR-06/RP-11(R11-07): DB 루프만이 아니라 conversation 작업 부하 포함.
        try:
            snap = _profiled(
                2,
                lambda: conv_store.append(
                    project_id="soak",
                    conversation_id="soak-conv",
                    expected_revision=conv_rev,
                    role="user",
                    content=f"soak turn {i}",
                ),
            )
            _lap(2)
            conv_rev = snap.revision
            conv_ops += 1
        except Exception:
            errors += 1
        if _deep_phase[0] is None:
            attribution_measured_ops += 1
        _clock[0] = time.process_time()  # 루프·표본 비용은 국면에 안 붙인다(잔차로 남긴다)
        i += 1
        if i % 50 == 0:
            # NX-04: 계측 overhead 를 실측해 보고한다(샘플링이 soak 를 지배하지 않음).
            _t0 = time.perf_counter()
            sample_times_s.append(time.time() - started)
            sample_ops.append(i)
            sample_cpu_s.append(time.process_time())
            try:
                sample_load1.append(float(os.getloadavg()[0]))
            except (OSError, AttributeError):  # 부하 계기를 못 읽으면 “모름”(-1)으로 남긴다
                sample_load1.append(-1.0)
            rss_samples.append(_rss_mb())
            fd_samples.append(_fd_count())
            if i % ATTRIBUTION_SAMPLE_EVERY == 0:
                # 국면 누적 CPU 를 같은 시점에 스냅샷한다(세 국면의 길이가 항상 같다 — 그게 계약이다).
                for phase_index in range(len(SOAK_PHASES)):
                    attribution_cpu_s[phase_index].append(round(phase_cpu[phase_index], 3))
                attribution_ops.append(attribution_measured_ops)
                attribution_times_s.append(round(time.time() - started, 3))
            sample_overhead_s += time.perf_counter() - _t0
    # FR-06/RP-11: 실측 종료 시각 — 요청값이 아니라 실제로 흘린 시간을 기록한다.
    actual_duration = round(time.time() - started, 3)
    # SC-6 기준 재설계: 판정은 순수 함수가 한다(워밍업 창 밖 증가 + 반복당 creep). 입력은 리포트에
    # 실리는 반올림 값과 같게 맞춘다 — 리포트만 보고도 같은 판정을 재현할 수 있어야 한다.
    rss_verdict = sc6_rss_criterion([round(r, 1) for r in rss_samples], sample_ops, sample_times_s, actual_duration)
    # 처리량 회귀는 **RSS 와 다른 축**이다(둘은 서로를 대신하지 못한다 — 계약 시험이 네 조합을 고정한다).
    throughput_verdict = throughput_criterion(
        sample_ops,
        [round(t, 3) for t in sample_times_s],
        [round(c, 3) for c in sample_cpu_s],
        sample_load1,
        os.cpu_count() or 1,
        actual_duration,
    )
    # 귀속 사다리: **게이트가 빨간 실행에서만** 돈다(초록이면 `not_applicable` · 판정을 바꾸지 않는다).
    attribution_verdict = throughput_attribution(
        SOAK_PHASES,
        attribution_cpu_s,
        attribution_ops,
        attribution_times_s,
        sample_ops,
        [round(t, 3) for t in sample_times_s],
        [round(c, 3) for c in sample_cpu_s],
        throughput_verdict,
        actual_duration,
    )
    # 프로파일 원자료는 **한 번만** 만든다: 두 칸(국면 내부 · 호출 경로)이 **같은 자료**를 보아야 하고,
    # 리포트에 실리는 것도 그 자료다(읽는 사람과 계산하는 사람이 같은 것을 본다).
    deep_profile = profiler.report()
    # 사다리의 **다음 칸**: 앞칸이 국면을 지목했을 때만 그 국면 **안**의 함수 순위를 낸다.
    deep_verdict = phase_function_attribution(
        attribution_verdict.get("attribution_phase"),
        deep_profile,
        attribution_verdict,
        actual_duration,
    )
    # **네 번째 칸**: 앞 칸이 함수를 지목했을 때만 그 함수를 **누가·얼마나 자주** 부르는지 좁힌다.
    path_verdict = function_call_path(deep_verdict, deep_profile, actual_duration)
    criteria_ok, criteria_why = criteria_gate(rss_verdict, throughput_verdict, actual_duration)
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
        "criteria_gate": criteria_why,
        "rss_samples_mb": [round(r, 1) for r in rss_samples],
        **rss_verdict,
        **throughput_verdict,
        **attribution_verdict,
        **deep_verdict,
        **path_verdict,
        # 원자료도 싣는다: 다음 사람이 같은 함수 순위·호출 경로를 리포트만으로 다시 낼 수 있어야 한다.
        "deep_profile": deep_profile,
        "fd_samples": fd_samples,
        "fd_growth": fd_growth,
        "orphan_worktrees": orphan_wt,
        "db_accessible_after": lock_ok,
        "pass": (
            errors == 0
            # RSS 는 두 축(창 밖 증가 · 반복당 creep)으로 본다 — 판정 불가(not_applicable)는 통과가 아니다.
            and rss_verdict["rss_criterion"] != "fail"
            # 두 축은 **독립**이고, 긴 실행에서는 `not_applicable` 도 통과가 아니다(`criteria_gate` 참조).
            and criteria_ok
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
            "rss_warmup_min_s": RSS_WARMUP_MIN_S,
            "rss_warmup_fraction": RSS_WARMUP_FRACTION,
            "rss_creep_max_kb_per_op": RSS_CREEP_MAX_KB_PER_OP,
            "throughput_max_decline": THROUGHPUT_MAX_DECLINE,
            "throughput_min_run_s": THROUGHPUT_MIN_RUN_S,
            "throughput_block_min_s": THROUGHPUT_BLOCK_MIN_S,
            "throughput_host_load_max": THROUGHPUT_HOST_LOAD_MAX,
            "attribution_dominance": ATTRIBUTION_DOMINANCE,
            "attribution_min_delta_ratio": ATTRIBUTION_MIN_DELTA_RATIO,
            "attribution_sample_every": ATTRIBUTION_SAMPLE_EVERY,
            "attribution_outside_gap_ratio": ATTRIBUTION_OUTSIDE_GAP_RATIO,
            "deep_sample_every": DEEP_SAMPLE_EVERY,
            "deep_window_calls": DEEP_WINDOW_CALLS,
            "deep_max_windows": DEEP_MAX_WINDOWS,
            "deep_max_ops": DEEP_MAX_OPS,
            "deep_function_dominance": DEEP_FUNCTION_DOMINANCE,
            "deep_outside_ratio": DEEP_OUTSIDE_RATIO,
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
