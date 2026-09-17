#!/usr/bin/env python
"""NX-10 — 8시간 soak **회수 스크립트** (아침에 이거 하나만 돌린다).

왜 스크립트인가: soak 판정은 "JSON 지표를 읽는다"가 아니다. 카드는 **지표 + 시작/종료 지문 동일 +
exit 의미**를 함께 본다. 손으로 tail 하다 보면 지표만 보고 "통과"라고 쓰기 쉬운데, 이 프로젝트는
그 실수(EX-05 승격: 종료·귀속이 미확정인데 PASS 로 올림)를 이미 한 번 겪었다. 그래서 회수 판정도
코드로 고정하고, 판정 함수를 따로 두어 **검사기 자체를 시험**할 수 있게 만들었다.

판정 3단계(모두 통과해야 PASS):
  ① **지표** — `soak-28800.json` 의 `all_pass` 가 true 이고 `missing_required` 가 비었는가
  ② **실행** — 러너가 남긴 `exit` 가 0 이고, 시작→종료 **벽시계**가 요청 시간 이상인가
     (즉시 실패한 실행도 리포트는 쓴다 — duration 을 봐야 걸러진다)
  ③ **귀속** — 기대 지문(예약 기록) == 시작 지문 == 종료 지문 == **지금 작업 트리 지문**
     (마지막 항등식은 "soak 이후 코드가 움직이지 않았다"를 뜻한다. 깨지면 그 green 은 후보의 것이 아니다)

실행(승격 뒤 — 이 파일은 `scripts/` 에 있고, 증거는 계속 `docs/qa/…/nx10/` 에 쓴다):
    python3 scripts/collect_soak_result.py
    … --wait                 # 아직 돌고 있으면 끝날 때까지 기다린다(30초 간격)
    … --selftest             # 합성 입력으로 PASS/FAIL 구분을 검증한다(증거를 건드리지 않는다)
`NX10_SOAK_OUT` 으로 증거 디렉터리를 바꿀 수 있다.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path


def _repo_root() -> Path:
    """저장소 루트 — **자기 파일 위치의 깊이에 의존하지 않는다**.

    이 판정기는 스테이징(`docs/qa/2026-09-16-followup/nx10/`)과 승격 위치(`scripts/`) 양쪽에서
    돌아야 한다. `parents[4]` 는 스테이징에서만 맞고, 승격 뒤에는 엉뚱한 디렉터리를 저장소로
    믿는다(같은 깊이 가정을 쓰던 `verify_docs_commands.py` 가 실제로 그렇게 죽었다).
    증거 파일 경로(`OUT`)는 아래에서 **루트 기준**으로 파생된다 — 판정기가 어디 있든
    회수 기록은 `docs/qa/2026-09-16-followup/nx10/` 에 쓰인다.
    """
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise RuntimeError("저장소 루트를 찾지 못했다(pyproject.toml 없음)")


REPO = _repo_root()
OUT = Path(os.environ.get("NX10_SOAK_OUT") or (REPO / "docs" / "qa" / "2026-09-16-followup" / "nx10"))
EXIT_LOG = OUT / "soak-exit.txt"
SCHEDULE = OUT / "soak-schedule.txt"
SOAK_SECONDS = 28800

SCENARIO_KEYS_TO_SHOW = (
    "workers",
    "tasks",
    "total_wins",
    "terminal_contradictions",
    "cross_owner_leak",
    "unexpected_errors",
    "duration_s",
    "requested_duration_s",
    "stream_line_count",
    "rss_start_mb",
    "rss_end_mb",
    "fd_start",
    "fd_end",
    "orphan_worktrees",
    "errors",
    "p95_ms",
    "p99_ms",
)


@dataclass(frozen=True)
class Check:
    label: str
    ok: bool
    detail: str


def now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# ── 파싱 ────────────────────────────────────────────────────────────────


def parse_exit_blocks(text: str) -> list[dict[str, str]]:
    """`soak-exit.txt` 의 러너 블록들(‘# NX-10 …러너 기록’ 로 시작)을 파싱한다."""
    blocks: list[dict[str, str]] = []
    current: dict[str, str] | None = None
    for line in text.splitlines():
        if line.startswith("# NX-10 SC-1~6 soak"):
            current = {}
            blocks.append(current)
            continue
        if current is None or not line.strip() or line.lstrip().startswith("#"):
            continue
        match = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if match:
            current[match.group(1)] = match.group(2).strip()
    return blocks


def latest_finished_block(blocks: list[dict[str, str]], seconds: int) -> dict[str, str] | None:
    """요청한 길이의 블록 중 **마지막 완료 블록**. 60초 리허설과 8시간 실행을 섞지 않는다."""
    finished = [b for b in blocks if "exit" in b and b.get("soak_seconds") == str(seconds)]
    return finished[-1] if finished else None


def seconds_between(start: str, end: str) -> float | None:
    try:
        fmt = "%Y-%m-%dT%H:%M:%SZ"
        a = datetime.strptime(start, fmt).replace(tzinfo=timezone.utc)
        b = datetime.strptime(end, fmt).replace(tzinfo=timezone.utc)
    except (ValueError, TypeError):
        return None
    return (b - a).total_seconds()


_EXPECTED_FP_RE = re.compile(r"^expected_fingerprint:\s*(\S+)$", re.M)
# 예약 블록의 머리 — 통제 도구(`soak_control.sh`)가 예약을 걸 때마다 이 줄로 새 블록을 시작한다.
_SCHEDULE_BLOCK_RE = re.compile(r"^#\s*NX-10 soak 예약 기록", re.M)
# 중단 표시 — 이 블록은 **한 틱도 돌지 않았다**는 뜻이다(`start_check_fingerprint: UNVERIFIED` 와 함께 쓰인다).
_ABORTED_RE = re.compile(r"^aborted:\s*(?:true|yes|1)\s*$", re.I | re.M)


def _schedule_text() -> str:
    return SCHEDULE.read_text(encoding="utf-8") if SCHEDULE.is_file() else ""


def schedule_blocks(text: str) -> list[str]:
    """예약 이력을 블록으로 나눈다 — 헤더가 하나도 없으면 전체를 한 블록으로 본다.

    헤더 0건 = 단일 블록으로 두는 이유: 계약 시험이 쓰는 합성 입력은 헤더 없이 기대 지문만 적는다.
    그 입력에서도 종전 동작(“마지막 매치”)이 그대로 나와야 회귀가 아니다.
    """
    starts = [m.start() for m in _SCHEDULE_BLOCK_RE.finditer(text)]
    if not starts:
        return [text] if text.strip() else []
    bounds = [*starts, len(text)]
    return [text[bounds[i] : bounds[i + 1]] for i in range(len(starts))]


def is_aborted_block(block: str) -> bool:
    """중단된 예약인가 — 중단은 “그 트리에서 아무것도 재지 않았다”와 같은 말이다."""
    return _ABORTED_RE.search(block) is not None


def latest_expected_fingerprint(text: str) -> str:
    """예약 기록에서 **살아 있는 마지막** 기대 지문(중단된 블록은 기대값이 아니다).

    이 함수는 두 번 틀렸고, 두 번 다 “지표는 PASS 인데 판정 근거가 없는” 상태를 만들었다:

    ① **첫 매치**(2026-09-16) — 이 파일은 예약할 때마다 블록을 **덧붙인다**(재장전·취소 기록도 쌓인다).
       `re.search` 는 첫 값을 잡았고, 그날 첫 값은 `157311cf…`(08:20Z) · 현재 예약은
       `92fcaeb5…`(11:39Z) 였다 → 밤새 정상으로 끝난 실행이 거짓 FAIL 이 될 뻔했다(고침: 마지막).
    ② **중단된 예약**(2026-09-17) — 마지막 두 블록이 `aborted: true`(예약 시점에 지문을 못 재
       `start_check_fingerprint: UNVERIFIED`)였다. 그 예약들은 한 틱도 돌지 않았는데, 지표 all_pass ·
       러너 exit 0 · 벽시계 28804s · 시작==종료==현재 트리(`b6a74304…`)로 끝난 8시간 실행이
       그 지문(`322b4d3b…`)과 달라 **거짓 FAIL** 로 판정됐다(고침: 중단 블록은 건너뛴다).

    살아 있는 예약이 하나도 없으면 `UNVERIFIED` 를 돌려준다 — 그때는 `resolve_expected()` 가 러너가
    스스로 기록한 시작 지문으로 내려가되 **출처를 밝힌다**(조용히 통과시키지 않는다).

    `previous_expected_fingerprint:` 같은 다른 키는 줄 시작 앵커(`^`) 때문에 걸리지 않는다.
    """
    for block in reversed(schedule_blocks(text)):
        if is_aborted_block(block):
            continue
        matches = _EXPECTED_FP_RE.findall(block)
        if matches:
            return matches[-1]
    return "UNVERIFIED"


def reservation_count(text: str | None = None) -> int:
    """이 파일에 기록된 예약 이력 수 — 판정 출력에 붙여 “어느 예약을 썼는지”를 보이게 한다."""
    return len(_EXPECTED_FP_RE.findall(_schedule_text() if text is None else text))


def expected_fingerprint(override: str | None = None) -> str:
    if override:
        return override
    return latest_expected_fingerprint(_schedule_text())


def resolve_expected(override: str | None, block: dict[str, str] | None = None) -> tuple[str, str]:
    """기대 지문과 **그 출처**(사람이 읽는 한 줄)를 함께 돌려준다.

    왜 출처를 함께 남기는가: 이 카드가 반복해서 물린 지점이 “판정 근거가 무엇이었는가”다. 근거가
    예약 기록인지 · 사람이 지정한 것인지 · 러너의 자기 기록인지가 출력과 JSON 에 남지 않으면,
    같은 값을 두고 “PASS 가 어디서 왔는지”를 나중에 아무도 재구성할 수 없다.

    즉시 실행(`soak_control.sh run`)은 예약 블록을 **남기지 않는다** — 그때 살아 있는 예약이 없다고
    FAIL 로 몰면 정상 실행이 매번 거짓 FAIL 이 되고(2026-09-17 실측), 아무 근거 없이 PASS 로 두면
    “기대 == 시작” 검사가 조용히 사라진다. 그래서 러너가 스스로 기록한 시작 지문을 쓰고,
    그 사실을 출처 문장으로 밝힌다.
    """
    if override:
        return override, "사람이 지정(--expected-fingerprint)"
    live = latest_expected_fingerprint(_schedule_text())
    if live != "UNVERIFIED":
        return live, f"soak-schedule.txt 살아 있는 예약 {reservation_count()}건 중 마지막(중단 블록 제외)"
    runner_fp = str((block or {}).get("start_fingerprint") or "")
    if runner_fp:
        return runner_fp, "예약 기록 없음(즉시 실행) → 러너가 기록한 시작 지문"
    return "UNVERIFIED", "근거 없음(살아 있는 예약도 러너 기록도 없다)"


def _interpreter() -> str:
    """지문을 재는 인터프리터: 저장소 venv(게이트와 같은 도구)가 있으면 그것, 없으면 지금 파이썬.

    `.venv` 를 하드 요구하면 승격 뒤 다른 트리(리허설 미러·새 클론·CI 샌드박스)에서 죽는다.
    """
    venv_py = REPO / ".venv" / "bin" / "python"
    return str(venv_py) if venv_py.is_file() else sys.executable


def fingerprint_now() -> str:
    proc = subprocess.run(
        [
            _interpreter(),
            "-c",
            "import sys,pathlib; sys.path.insert(0,'scripts'); import ga_gate; "
            "print(ga_gate.worktree_fingerprint(pathlib.Path('.')))",
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    return proc.stdout.strip() or "UNVERIFIED"


def soak_still_running() -> bool:
    return subprocess.run(["pgrep", "-f", "val02_staging.py"], capture_output=True, text=True).returncode == 0


# ── 판정 (검사기 자체를 시험할 수 있도록 순수 함수로 둔다) ──────────────


def judge(
    *,
    block: dict[str, str],
    report: dict[str, object] | None,
    expected_fp: str,
    now_fp: str,
    seconds: int,
    expected_source: str = "예약 기록",
) -> tuple[str, list[Check]]:
    checks: list[Check] = []

    # ① 지표
    if report is None:
        checks.append(Check("① 지표(all_pass·missing_required)", False, "리포트 없음(러너가 종료 시에만 쓴다)"))
    else:
        reasons = []
        if report.get("all_pass") is not True:
            reasons.append(f"all_pass={report.get('all_pass')!r}")
        missing = report.get("missing_required") or []
        if missing:
            reasons.append(f"missing_required={missing}")
        checks.append(Check("① 지표(all_pass·missing_required)", not reasons, "; ".join(reasons) or "all_pass=true"))

    # ② 실행
    exit_code = block.get("exit")
    duration = seconds_between(str(block.get("start_time")), str(block.get("end_time")))
    detail_exit = f"exit={exit_code}" + (" (143=SIGTERM: 중단됨)" if exit_code == "143" else "")
    checks.append(Check("② 실행 exit==0", exit_code == "0", detail_exit))
    checks.append(
        Check(
            f"② 실행 벽시계 ≥ {seconds}s",
            duration is not None and duration >= seconds,
            f"{duration:.0f}s" if duration is not None else "시각 파싱 실패 — 중단/재시작을 의심",
        )
    )

    # ③ 귀속
    start_fp = str(block.get("start_fingerprint") or "")
    end_fp = str(block.get("end_fingerprint") or "")
    same_run = bool(start_fp) and start_fp == end_fp
    checks.append(
        Check(
            "③ 시작 지문 == 종료 지문",
            same_run,
            f"{start_fp[:16]}…" if same_run else f"{start_fp[:16]}… ≠ {end_fp[:16]}…",
        )
    )
    checks.append(
        Check(
            "③ 기대 지문 == 시작 지문",
            expected_fp != "UNVERIFIED" and expected_fp == start_fp,
            f"{expected_fp[:16]}… (출처: {expected_source})",
        )
    )
    checks.append(
        Check(
            "③ 지금 트리 == 시작 지문(측정 후 코드 무변경)",
            now_fp == start_fp,
            "동일" if now_fp == start_fp else "달라짐 → 이 green 은 후보의 것이 아니다",
        )
    )

    metrics_ok = checks[0].ok
    run_ok = checks[1].ok and checks[2].ok
    if all(c.ok for c in checks):
        verdict = "PASS"
    elif metrics_ok and not run_ok:
        verdict = "METRICS_PASS / 실행·귀속 INCONCLUSIVE — DONE 아님"
    else:
        verdict = "FAIL"
    return verdict, checks


def show_report(path: Path) -> tuple[dict[str, object] | None, Path]:
    if not path.is_file():
        return None, path
    return json.loads(path.read_text(encoding="utf-8")), path


def print_scenarios(data: dict[str, object]) -> None:
    scenarios = data.get("scenarios") or []
    if not isinstance(scenarios, list):
        return
    for scenario in scenarios:
        if not isinstance(scenario, dict):
            continue
        flag = "pass" if scenario.get("pass") else "FAIL"
        detail = " ".join(
            f"{k}={scenario[k]}" for k in SCENARIO_KEYS_TO_SHOW if k in scenario and scenario[k] is not None
        )
        print(f"    [{flag}] {scenario.get('scenario', '?')}: {detail}")


# ── 자체 시험 ───────────────────────────────────────────────────────────


def selftest() -> int:
    """판정 로직이 PASS 를 남발하지 않는지 합성 입력으로 검증한다(증거 디렉터리를 읽지 않는다)."""
    fp = "a" * 64
    base = {
        "soak_seconds": "28800",
        "start_time": "2026-09-16T13:00:00Z",
        "end_time": "2026-09-16T21:00:10Z",
        "start_fingerprint": fp,
        "end_fingerprint": fp,
        "exit": "0",
    }
    good_report: dict[str, object] = {"all_pass": True, "missing_required": [], "scenarios": []}
    cases: tuple[tuple[str, dict[str, str], dict[str, object] | None, str, str], ...] = (
        ("정상", {**base}, good_report, fp, "PASS"),
        (
            "중단(exit 143, 20분)",
            {**base, "exit": "143", "end_time": "2026-09-16T13:20:00Z"},
            good_report,
            fp,
            "METRICS_PASS",
        ),
        ("지문 불일치(시작≠종료)", {**base, "end_fingerprint": "b" * 64}, good_report, fp, "FAIL"),
        ("지표 실패", {**base}, {"all_pass": False, "missing_required": ["SC-6"], "scenarios": []}, fp, "FAIL"),
        ("측정 후 코드 변경", {**base}, good_report, "c" * 64, "FAIL"),
        ("리포트 없음", {**base}, None, fp, "FAIL"),
    )
    failures = 0
    total = 0
    for label, block, report, now_fp, want in cases:
        total += 1
        verdict, _ = judge(block=block, report=report, expected_fp=fp, now_fp=now_fp, seconds=28800)
        matched = verdict == want or (want == "METRICS_PASS" and verdict.startswith("METRICS_PASS"))
        print(f"  [{'OK ' if matched else 'NO '}] {label}: verdict={verdict!r} (기대 {want})")
        failures += 0 if matched else 1

    # 예약 기록 판독 — 이 프로젝트는 재장전을 여러 번 하므로 “첫 예약”을 잡으면 거짓 FAIL 이 된다.
    schedule_cases: tuple[tuple[str, str, str], ...] = (
        (
            "예약 이력 3건 → 마지막을 쓴다",
            "".join(f"expected_fingerprint: {n * 64}\n" for n in ("1", "2", "3")),
            "3" * 64,
        ),
        ("이력 없음 → UNVERIFIED", "# 예약 없음\n", "UNVERIFIED"),
        (
            "previous_expected_fingerprint 는 세지 않는다",
            "previous_expected_fingerprint: " + "d" * 64 + "\n",
            "UNVERIFIED",
        ),
        (
            "중단된 마지막 예약은 건너뛰고 그 앞의 살아 있는 예약을 쓴다",
            "# NX-10 soak 예약 기록\n"
            f"expected_fingerprint: {'4' * 64}\n"
            "# NX-10 soak 예약 기록\n"
            f"expected_fingerprint: {'5' * 64}\naborted: true\n",
            "4" * 64,
        ),
        (
            "살아 있는 예약이 하나도 없으면 UNVERIFIED(중단뿐인 이력)",
            f"# NX-10 soak 예약 기록\nexpected_fingerprint: {'6' * 64}\naborted: true\n",
            "UNVERIFIED",
        ),
    )
    for label, text, want in schedule_cases:
        total += 1
        got = latest_expected_fingerprint(text)
        matched = got == want
        print(f"  [{'OK ' if matched else 'NO '}] {label}: 기대지문={got[:16]}… (기대 {want[:16]}…)")
        failures += 0 if matched else 1
    print(f"selftest: {total - failures}/{total}")
    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="NX-10 soak 회수 판정")
    parser.add_argument("--wait", action="store_true", help="끝날 때까지 기다린다(30초 간격)")
    parser.add_argument("--timeout-min", type=float, default=30.0, help="--wait 최대 대기(분)")
    parser.add_argument("--seconds", type=int, default=SOAK_SECONDS, help="요청한 soak 길이(초)")
    parser.add_argument("--expected-fingerprint", default=None, help="기대 지문 직접 지정(기본: soak-schedule.txt)")
    parser.add_argument("--selftest", action="store_true", help="판정 로직만 시험한다(아티팩트를 읽지 않는다)")
    args = parser.parse_args()

    if args.selftest:
        return selftest()

    report_path = OUT / f"soak-{args.seconds}.json"
    deadline = time.time() + args.timeout_min * 60
    while True:
        blocks = parse_exit_blocks(EXIT_LOG.read_text(encoding="utf-8")) if EXIT_LOG.is_file() else []
        block = latest_finished_block(blocks, args.seconds)
        running = soak_still_running()
        if block is not None and not running:
            break
        if not args.wait or time.time() > deadline:
            print(f"[{now()}] 아직 회수할 실행이 없다.")
            print(
                f"  러너 블록 {len(blocks)}개 · {args.seconds}s 완료 블록 {'있음' if block else '없음'} · 실행 중={'예' if running else '아니오'}"
            )
            print(f"  리포트 {report_path.name}: {'있음' if report_path.is_file() else '없음'}")
            print("  → 아직 돌고 있으면 `--wait`, 예약이 시작 전이면 soak-schedule.log 를 본다.")
            return 2
        print(f"[{now()}] 대기 중… (완료 블록 없음 또는 실행 중)")
        time.sleep(30)

    data, _ = show_report(report_path)
    expected, expected_source = resolve_expected(args.expected_fingerprint, block)
    now_fp = fingerprint_now()
    verdict, checks = judge(
        block=block,
        report=data,
        expected_fp=expected,
        now_fp=now_fp,
        seconds=args.seconds,
        expected_source=expected_source,
    )

    print(f"=== NX-10 soak 회수 판정 ({now()}) ===")
    print(f"  러너: 시작 {block.get('start_time')} → 종료 {block.get('end_time')} · exit {block.get('exit')}")
    print(
        f"  지문: start={str(block.get('start_fingerprint'))[:16]}… end={str(block.get('end_fingerprint'))[:16]}… "
        f"기대={expected[:16]}… 지금={now_fp[:16]}…"
    )
    print(f"  기대 지문 출처: {expected_source}")
    if data:
        print(f"  리포트: {report_path.name} · generated_at {data.get('generated_at')} · workdir {data.get('workdir')}")
        print(f"    thresholds: {json.dumps(data.get('thresholds', {}), ensure_ascii=False)}")
        print_scenarios(data)
        rows = data.get("scenarios")
        scenarios = rows if isinstance(rows, list) else []  # `object` 를 그대로 돌리면 타입 오류다
        sc6 = next(
            (s for s in scenarios if isinstance(s, dict) and "SC-6" in str(s.get("scenario"))),
            None,
        )
        if sc6 is not None and "stream_line_count" not in sc6:
            print(
                "    [참고] SC-6 에 `stream_line_count` 계측값이 없다 — NX-04 가 남긴 8h 규모 미실측 항목은 이 실행으로 닫히지 않는다."
            )

    print("\n  ── 판정 ──")
    for check in checks:
        print(f"    [{'OK  ' if check.ok else 'NO  '}] {check.label} — {check.detail}")
    failed = [c.label for c in checks if not c.ok]
    print(f"\n  판정: {verdict}" + (f" (미충족: {', '.join(failed)})" if failed else ""))
    print("  ※ 지표만 통과한 상태를 'soak PASS'로 승격하지 않는다 — 카드는 지표 + 지문 동일을 요구한다.")

    print("\n  ── 다음 단계 ──")
    print("    1) 이 판정을 대장 §12 에 회수 행으로 추가한다(GATE_LEDGER.md).")
    print("    2) PASS 라면: 커밋(3분할, `git add -A` 금지) → `bash run_clean_machine_gate.sh` 로 후보 값 확보.")
    print("    3) 그 다음: CR-14 후보 재선언 → EX-05 판정 → ga_gate_verify 재실행 → 판정 문서 갱신.")
    print("    4) FAIL/INCONCLUSIVE 라면: 미충족 항목을 원인으로 적고, '돌리다 만 것'과 '의도적으로")
    print("       끊은 것'을 구분해 남긴다 — 중단 실행도 지우지 않는다(대장 §10 참조).")
    print("    전체 순서: CLOSURE_RUNBOOK.md §1~§4 · 결정 대기: GA_OWNER_DECISION_PACKET.md D1~D8")

    # 실행별 산출물은 덮어쓰지 않는다(중단 실행·최종 실행이 섞이면 판정 근거가 흔들린다) —
    # 실행 시작시각을 붙인 파일 + “마지막 판정”을 가리키는 최신 파일을 둘 다 쓴다.
    run_start = re.sub(r"[^0-9TZ]", "", str(block.get("start_time") or "unknown"))
    payload = json.dumps(
        {
            "collected_at": now(),
            "verdict": verdict,
            "judged_run_start": block.get("start_time"),
            "expected_fingerprint": expected,
            "expected_source": expected_source,
            "runner": block,
            "checks": [{"label": c.label, "ok": c.ok, "detail": c.detail} for c in checks],
            "report_file": report_path.name,
            "report_present": report_path.is_file(),
            "duration_seconds": seconds_between(str(block.get("start_time")), str(block.get("end_time"))),
            "worktree_fingerprint_now": now_fp,
        },
        ensure_ascii=False,
        indent=2,
    )
    (OUT / f"soak-recovery-{run_start}.json").write_text(payload, encoding="utf-8")
    (OUT / "soak-recovery-latest.json").write_text(payload, encoding="utf-8")
    with (OUT / "soak-recovery.log").open("a", encoding="utf-8") as handle:
        handle.write(f"--- {now()} run={block.get('start_time')} verdict={verdict} ---\n")
        for check in checks:
            handle.write(f"  [{'OK' if check.ok else 'NO'}] {check.label} — {check.detail}\n")
    print(f"\n  기록: {OUT.name}/soak-recovery-{run_start}.json (+ soak-recovery-latest.json) · soak-recovery.log")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
