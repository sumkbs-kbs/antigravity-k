"""NX-10 무인 체인 상태판 — **읽기 전용**. 죽은 뒤 다음 사람이 처음부터 읽지 않게 한다.

왜 필요한가(2026-09-17~18 실측):
    세션이 죽으면 **무인 체인도 같이 죽는다**(재부팅이면 화면·프로세스가 0건). 그때 다음 사람은
    “어디까지 갔나”를 손으로 복원해야 했고, 실제로 그 복원이 이 창에서 한 번 실패했다 —
    승격 5건이 인덱스에 스테이징된 채 남아 있었는데도 “승격이 안 됐다”로 보였고, 배치 체인이
    **②관문에서 옳게 멈춰 있었다**는 사실은 `batchchain-record.md` 를 열어야만 보였다.

    그래서 이 도구는 그 복원을 **한 화면**으로 만든다. 근거는 문장이 아니라 **파일과 종료 코드**다:
    커밋(`git log`) · 게이트 리포트(`gate-report-*.json`) · 러너 블록(`soak-exit.txt`) · 판정
    (`soak-recovery-latest.json`) · 화면/프로세스(`screen -ls`·`pgrep`).

이 도구가 **하지 않는 것**:
    아무것도 쓰지 않는다(파일·화면·프로세스 어느 것도 만들지 않는다). 그래서 돌고 있는 체인의
    측정에 끼어들지 않는다 — 죽은 뒤에도, 도는 중에도 안전하게 볼 수 있다.

사용:
    .venv/bin/python docs/qa/2026-09-16-followup/nx10/batchchain/chain_status.py
    .venv/bin/python …/chain_status.py --json          # 기계 판독(다른 도구·시험이 쓴다)
    NX10_STATUS_ROOT=<가짜 트리> …/chain_status.py     # 시험이 픽스처로 돌린다

종료 코드: 0 = 읽었다(내용이 무엇이든). 1 = 근거 파일 자체를 찾지 못했다(트리 위치가 다르다).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, NamedTuple


# ── 배치(순서가 곧 계약이다: 코드가 강제한다 — PERF 는 SC6 뒤, FLUSH 는 PERF 뒤) ───────────────
class Batch(NamedTuple):
    name: str
    gate_label: str
    commit_subject: str


BATCHES: tuple[Batch, ...] = (
    Batch("SC6", "batch-sc6", "feat(nx10): judge SC-6 by the creep outside the warm-up window"),
    Batch("PERF", "batch-perf", "feat(nx10): make throughput loss a first-class verdict axis"),
    Batch("FLUSH", "batch-flush", "perf(nx10): read the journal tail once per append"),
    Batch("FLUSH2", "batch-flush2", "perf(nx10): stop rewriting the view on every append by default"),
)

# 살아 있는 무인 작업을 알아보는 이름들. 대괄호는 **자기 자신을 잡지 않기 위한 것**이다 —
# 이 도구의 argv 에도 같은 이름이 들어가므로, 순진한 패턴은 항상 “돌고 있다”로 답한다(실측 함정).
WATCHERS = (
    ("배치 체인", r"[r]un_batch_chain\.sh", "nx10batchchain"),
    ("게이트 러너", r"[r]un_promote_gates\.sh", "nx10gates3"),
    ("8시간 soak", r"val02_staging[.]py", "nx10soak"),
    ("감시 루프", r"[s]oak_watch_loop\.py", "nx10watch"),
    ("회수 대기", r"[s]oak_control\.sh harvest", "nx10harvest"),
)


def repo_root(start: Path) -> Path:
    """`pyproject.toml` 을 위로 찾아 올라간다(이 파일이 승격·이동돼도 산다)."""
    for candidate in [start, *start.parents]:
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise FileNotFoundError("저장소 루트를 찾지 못했다 — pyproject.toml 이 없다")


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def run_readonly(command: list[str]) -> str:
    """읽기 전용 외부 명령. 실패해도 빈 문자열(모르는 것을 아는 척하지 않는다)."""
    try:
        done = subprocess.run(command, capture_output=True, text=True, timeout=20, check=False)
    except (OSError, subprocess.SubprocessError):
        return ""
    return done.stdout


# ── 1. 살아 있는 것 ───────────────────────────────────────────────────────────────────────────
def process_lookup(pid: int) -> tuple[int, str] | None:
    """pid → (부모 pid, 명령줄). 읽기 전용(외부 `ps`)."""
    out = run_readonly(["ps", "-o", "ppid=,command=", "-p", str(pid)]).strip()
    if not out:
        return None
    parent, _, command = out.partition(" ")
    try:
        return int(parent), command.strip()
    except ValueError:
        return None


def is_gate_child(pid: int, lookup: Any = None, depth: int = 5) -> bool:
    """이 프로세스가 **게이트가 돌리는 시험의 자식**인가.

    왜 필요한가(첫 실행에서 실측): 게이트 `python-tests` 는 `soak_control.sh --selftest` 를 돌리고, 그
    자기시험이 **진짜 `soak_control.sh harvest` 를 자식으로 띄운다**. 그대로 두면 상태판이 그것을
    “회수 대기”라는 **무인 작업**으로 보고한다 — 상태판이 거짓말을 하면 안 되므로 부모를 따라 올라가
    `pytest`/`selftest` 가 나오면 무인 작업에서 뺀다(대신 `시험 중`으로 밝힌다).
    """
    lookup = lookup or process_lookup
    current = pid
    for _ in range(depth):
        parent = lookup(current)
        if parent is None:
            return False
        parent_pid, command = parent
        if "selftest" in command or "pytest" in command:
            return True
        if parent_pid <= 1 or parent_pid == current:
            return False
        current = parent_pid
    return False


def live_jobs(lookup: Any = None) -> list[dict[str, Any]]:
    """무인 작업 목록. 게이트가 돌리는 **시험의 자식**은 무인 작업이 아니다(별도로 밝힌다)."""
    lookup = lookup or process_lookup
    screens = run_readonly(["screen", "-ls"])
    found: list[dict[str, Any]] = []
    for label, pattern, screen_name in WATCHERS:
        lines = run_readonly(["pgrep", "-fl", pattern]).strip().splitlines()
        pids: list[int] = []
        for line in lines:
            head = line.split(" ", 1)[0]
            pids.append(int(head)) if head.isdigit() else None
        real = [pid for pid in pids if not is_gate_child(pid, lookup)]
        attached = screen_name in screens
        if real or attached:
            found.append({"label": label, "processes": len(real), "screen": screen_name if attached else None})
        elif pids:
            found.append({"label": label, "processes": 0, "screen": None, "kind": "시험 중(게이트가 돌린 자식)"})
    return found


# ── 2. 배치 진행 ──────────────────────────────────────────────────────────────────────────────
def recent_commits(repo: Path, limit: int = 60) -> list[str]:
    out = run_readonly(["git", "-C", str(repo), "log", f"-{limit}", "--format=%h %s"])
    return [line for line in out.splitlines() if line.strip()]


def gate_summary(nx10: Path, label: str) -> dict[str, Any] | None:
    """게이트 리포트에서 **요약과 측정 지문**을 읽는다(문장을 긁지 않는다)."""
    report = nx10 / f"gate-report-{label}.json"
    if not report.is_file():
        return None
    try:
        doc = json.loads(read_text(report))
    except json.JSONDecodeError:
        return {"summary": None, "parse_error": True}
    git = doc.get("git") or {}
    verify = nx10 / f"gate_verify-{label}.txt"
    verdict = None
    if verify.is_file():
        try:
            verdict = (json.loads(read_text(verify)) or {}).get("verdict")
        except json.JSONDecodeError:
            verdict = None
    return {
        "summary": doc.get("summary") or {},
        "fingerprint": git.get("tree_fingerprint"),
        "head": git.get("sha"),
        "verdict": verdict,
        "gates": len(doc.get("gates") or []),
        "ids": [gate.get("id") for gate in doc.get("gates") or []],
    }


# 러너는 게이트를 **시작하기 전에** `[id] 명령` 한 줄을 남긴다(`run_promote_gates.sh` → `ga_gate.py`).
GATE_LINE = re.compile(r"^\[(?P<id>[a-z0-9][a-z0-9-]*)\] (?P<command>.+)$", re.M)
START_LINE = re.compile(r"^=== promote-gates START ", re.M)


def gate_progress(nx10: Path, collected: list[Any] | None) -> dict[str, Any] | None:
    """러너 로그에서 **지금 재고 있는 게이트 하나**와 그 경과를 읽는다.

    왜 필요한가(실측): 게이트 23개는 전부 `ga_gate.py` 안에서 돌아 **끝나야 리포트가 쓰인다**. 그래서
    리포트만 보면 “4/23 진행 중”까지밖에 못 말한다 — 어느 게이트인지, 얼마나 걸렸는지, 멈춘 것인지
    알려면 사람이 `ps` 를 두드려야 했다(이 창에서 실제로 그렇게 했다). 로그는 그 답을 이미 갖고 있다:
    게이트 출력은 로그로 흐르지 않으므로(실측: 12분째 `[python-tests]` 줄이 마지막이고 mtime 이 멈춰
    있었다) **줄 순서 ∧ 리포트의 id** 로 지금 재는 하나가 남는다.

    모르면 `None` 이다 — 없는 근거를 집지 않는다(로그가 다른 attempt 것이면 `state` 로 밝힌다).
    """
    path = nx10 / "promote-runner.log"
    text = read_text(path)
    if not text:
        return None
    starts = [match.start() for match in START_LINE.finditer(text)]
    if not starts:
        return None
    block = text[starts[-1] :]
    entries = [(match.group("id"), match.group("command")) for match in GATE_LINE.finditer(block)]
    if not entries:
        return None
    order = [entry[0] for entry in entries]
    done = [str(item) for item in (collected or [])]
    # 리포트의 id 들이 로그 순서의 **앞머리**가 아니면 이 로그 블록은 이 리포트의 attempt 가 아니다.
    if done != order[: len(done)]:
        return {"state": "다른 attempt 의 로그", "block_ids": len(order), "collected_ids": len(done)}
    running = next((entry for entry in entries if entry[0] not in set(done)), None)
    if running is None:
        return {"state": "끝", "id": order[-1] if order else None, "block_ids": len(order)}
    result: dict[str, Any] = {"state": "진행 중", "id": running[0], "command": running[1]}
    if order[-1] == running[0]:
        # 마지막 줄이 이 게이트의 줄이다 → 그 줄이 쓰인 시각(mtime)이 이 게이트가 시작된 시각이다.
        try:
            started = path.stat().st_mtime
        except OSError:
            return result
        result["started_unix"] = round(started, 3)
        result["elapsed_seconds"] = max(0, round(time.time() - started, 1))
    return result


def batch_states(repo: Path, nx10: Path) -> list[dict[str, Any]]:
    commits = recent_commits(repo)
    states: list[dict[str, Any]] = []
    for batch in BATCHES:
        commit = next((line for line in commits if batch.commit_subject in line), None)
        gates = gate_summary(nx10, batch.gate_label)
        partial = bool(gates) and gates.get("gates", 0) < EXPECTED_GATES
        states.append(
            {
                "batch": batch.name,
                "commit": commit,
                "applied": commit is not None,
                "gates": gates,
                "gates_complete": bool(gates) and gates.get("gates", 0) >= EXPECTED_GATES,
                "running_gate": gate_progress(nx10, gates.get("ids")) if partial else None,
            }
        )
    return states


def chain_stop(nx10: Path) -> dict[str, Any] | None:
    """체인이 스스로 멈춘 기록 — 마지막 `# 배치 체인 — 시작` **뒤**의 `## 중단` 블록만 본다.

    종전 회차의 중단이 남아 있어도 그것을 현재 상태로 오해하지 않는다(그것이 이 창에서
    실제로 났던 “없는 근거를 집는” 실수의 일반형이다).
    """
    record = nx10 / "batchchain" / "batchchain-record.md"
    text = read_text(record)
    if not text:
        return None
    starts = [m.start() for m in re.finditer(r"^# 배치 체인 — 시작 ", text, re.M)]
    if not starts:
        return None
    tail = text[starts[-1] :]
    stop = re.search(r"^## 중단 \((?P<at>[^)]+)\)\s*$(?P<body>.*?)(?=^#|\Z)", tail, re.M | re.S)
    if not stop:
        return None
    body = stop.group("body")
    step = re.search(r"^-\s*단계:\s*(\S+)", body, re.M)
    reason = re.search(r"^-\s*사유:\s*(.+)$", body, re.M)
    return {
        "at": stop.group("at"),
        "step": step.group(1) if step else "?",
        "reason": reason.group(1).strip() if reason else "?",
    }


# ── 3. soak 상태 ─────────────────────────────────────────────────────────────────────────────
BLOCK_MARKER = "# NX-10 SC-1~6 soak 러너 기록"
# 체인이 배치마다 재는 게이트 수(`run_promote_gates.sh` + `NX10_INCLUDE_CLEAN_MACHINE=1`).
EXPECTED_GATES = 23


def last_soak_block(nx10: Path) -> dict[str, Any] | None:
    text = read_text(nx10 / "soak-exit.txt")
    blocks = text.split(BLOCK_MARKER)
    if len(blocks) < 2:
        return None
    body = BLOCK_MARKER + blocks[-1]
    fields: dict[str, str] = {}
    for line in body.splitlines():
        match = re.match(r"^([a-z_]+):\s*(.*)$", line)
        if match:
            fields[match.group(1)] = match.group(2).strip()
    return {
        "start_time": fields.get("start_time"),
        "end_time": fields.get("end_time"),
        "exit": fields.get("exit"),
        "start_fingerprint": fields.get("start_fingerprint"),
        "end_fingerprint": fields.get("end_fingerprint"),
        "soak_seconds": fields.get("soak_seconds"),
        "workdir": fields.get("workdir"),
        "attributed": bool(
            fields.get("start_fingerprint")
            and fields.get("end_fingerprint")
            and fields["start_fingerprint"] == fields["end_fingerprint"]
        ),
    }


def last_verdict(nx10: Path) -> dict[str, Any] | None:
    path = nx10 / "soak-recovery-latest.json"
    if not path.is_file():
        return None
    try:
        doc = json.loads(read_text(path))
    except json.JSONDecodeError:
        return None
    runner = doc.get("runner") or {}
    return {
        "verdict": doc.get("verdict"),
        "collected_at": doc.get("collected_at"),
        "exit": runner.get("exit"),
        "judged_run_start": doc.get("judged_run_start"),
    }


# ── 4. 다음 할 일(파일 근거로만 계산한다) ──────────────────────────────────────────────────────
def next_action(states: list[dict[str, Any]], stop: dict[str, Any] | None, jobs: list[dict[str, Any]]) -> str:
    # **부분 리포트는 끝난 것이 아니다**(실측: 4/23 인 리포트를 “게이트 있다”로 세면 SC6 이 완료로 보이고
    # 다음 할 일이 PERF 로 넘어간다 — 실제로는 SC6 을 재고 있는 중이었다).
    pending = [state for state in states if not (state["applied"] and state["gates_complete"])]
    if stop and not any(job["label"] == "배치 체인" for job in jobs):
        return f"체인이 멈췄다(단계 {stop['step']} · {stop['at']}) — record 의 사유를 읽고 재개 여부를 정한다"
    if not pending:
        return "네 배치가 모두 적용·측정됐다 — 새 지문에서 soak 이 돌고 있는지 확인한다(아래 soak 상태)"
    current = pending[0]
    running = current.get("running_gate") or {}
    if current["applied"] and running.get("state") == "다른 attempt 의 로그":
        return f"{current['batch']} 게이트 리포트가 부분인데 러너 로그는 다른 attempt 다 — 상태를 단정하지 않는다"
    if current["applied"] and current["gates"]:
        where = f"지금 [{running['id']}]" if running.get("id") else "어느 게이트인지 로그에서 읽지 못했다"
        return f"{current['batch']} 게이트 23개가 도는 중이다({where}) — 끝나면 요약이 리포트에 붙는다"
    if current["applied"] and not current["gates"]:
        return f"{current['batch']} 게이트가 아직 시작 전이다 — 러너가 살아 있는지 확인한다"
    if not current["applied"]:
        return f"{current['batch']} 적용 전이다 — 체인이 살아 있는지 확인한다(없으면 재개)"
    return "상태를 판단할 수 없다"


def collect(root: Path, repo: Path | None = None) -> dict[str, Any]:
    """상태를 모은다. `repo` 를 주면 그 저장소의 `git log` 를 근거로 쓴다(시험 픽스처용).

    픽스처는 저장소 밖(`tmp`)에 있으므로 위로 올라가도 `pyproject.toml` 이 없다 — 그래서
    “루트 찾기”와 “무엇을 근거로 보는가”를 분리해 둔다.
    """
    repo = repo or repo_root(root)
    nx10 = root
    states = batch_states(repo, nx10)
    jobs = live_jobs()
    stop = chain_stop(nx10)
    return {
        "root": str(nx10),
        "live": jobs,
        "batches": states,
        "chain_stop": stop,
        "next": next_action(states, stop, jobs),
        "soak": {"last_block": last_soak_block(nx10), "verdict": last_verdict(nx10)},
    }


def running_gate_text(progress: dict[str, Any] | None) -> str:
    """지금 재고 있는 게이트 한 칸 — 경과는 **로그 줄이 쓰인 시각** 기준임을 숨기지 않는다."""
    if not progress:
        return ""
    if progress.get("state") == "다른 attempt 의 로그":
        return " · 지금 도는 게이트: **로그가 다른 attempt 라 단정하지 않는다**"
    if not progress.get("id"):
        return " · 지금 도는 게이트: 로그에서 읽지 못했다"
    elapsed = progress.get("elapsed_seconds")
    if elapsed is None:
        return f" · 지금 [{progress['id']}](경과 미상)"
    minutes, seconds = divmod(int(elapsed), 60)
    return f" · 지금 [{progress['id']}] (그 줄이 쓰인 뒤 {minutes}분 {seconds}초)"


def render(state: dict[str, Any]) -> str:
    lines: list[str] = []
    lines.append("=== 살아 있는 무인 작업 ===")
    if state["live"]:
        for job in state["live"]:
            if job.get("kind"):
                lines.append(f"  {job['label']}: {job['kind']} — 무인 작업으로 세지 않는다")
                continue
            screen = f" · 화면 {job['screen']}" if job["screen"] else " · 화면 없음(프로세스만)"
            lines.append(f"  {job['label']}: 프로세스 {job['processes']}건{screen}")
    else:
        lines.append("  없음 — 재부팅이면 여기서 0건이 된다(그 상태가 2026-09-18 에 실제로 있었다)")

    lines.append("")
    lines.append("=== 배치 진행 (순서: SC6 → PERF → FLUSH → FLUSH2) ===")
    for state_ in state["batches"]:
        gates = state_["gates"]
        if gates is None:
            gate_text = "게이트 리포트 없음"
        elif gates.get("parse_error"):
            gate_text = "리포트를 읽지 못했다"
        else:
            summary = gates["summary"]
            # `not_run` 은 0 일 때 리포트에 아예 없을 수 있다 — 없는 키를 `None` 으로 찍지 않는다.
            # 리포트는 **끝날 때까지 부분**이다(수집된 게이트 수만 들어 있다) — 그래서 23개와 비교해
            # “도는 중”을 드러낸다. 기준 23은 체인이 거는 게이트 수다(`NX10_INCLUDE_CLEAN_MACHINE=1`).
            collected = gates["gates"]
            progress = " — 진행 중" if collected < EXPECTED_GATES else " — 끝"
            gate_text = (
                f"게이트 {summary.get('passed')} passed · {summary.get('failed')} failed · "
                f"{summary.get('not_run', 0)} not_run (수집 {collected}/{EXPECTED_GATES}개{progress}) · "
                f"판정 {gates.get('verdict') or '(아직 없음)'}" + running_gate_text(state_.get("running_gate"))
            )
        commit = state_["commit"] or "커밋 없음"
        lines.append(f"  [{state_['batch']}] {commit} · {gate_text}")

    lines.append("")
    lines.append("=== soak ===")
    block = state["soak"]["last_block"]
    if block:
        match = "시작 == 종료(귀속 성립)" if block["attributed"] else "**갈렸다**"
        lines.append(
            f"  마지막 러너 블록: {block['start_time']} → {block['end_time'] or '실행 중'} · "
            f"exit {block['exit']} · 지문 {match}"
        )
        if block["workdir"]:
            lines.append(f"  작업디렉터리: {block['workdir']}")
    else:
        lines.append("  러너 기록을 찾지 못했다")
    verdict = state["soak"]["verdict"]
    if verdict:
        lines.append(
            f"  마지막 판정: {verdict['verdict']} (exit {verdict['exit']} · 수집 {verdict['collected_at']} · "
            f"대상 실행 {verdict['judged_run_start']})"
        )
    else:
        lines.append("  판정 JSON 없음")

    lines.append("")
    lines.append(f"=== 다음 할 일 ===\n  {state['next']}")
    if state["chain_stop"]:
        stop = state["chain_stop"]
        lines.append(f"\n  (마지막 중단 기록: 단계 {stop['step']} · {stop['at']} · {stop['reason']})")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NX-10 무인 체인 상태판(읽기 전용)")
    parser.add_argument("--json", action="store_true", help="기계 판독 JSON")
    parser.add_argument(
        "--root", default=os.environ.get("NX10_STATUS_ROOT") or str(Path(__file__).resolve().parent.parent)
    )
    parser.add_argument("--repo", default=os.environ.get("NX10_STATUS_REPO") or None)
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    try:
        state = collect(root, Path(args.repo).resolve() if args.repo else None)
    except FileNotFoundError as error:
        print(f"[FAIL] {error}", file=sys.stderr)
        return 1
    print(json.dumps(state, ensure_ascii=False, indent=2) if args.json else render(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
