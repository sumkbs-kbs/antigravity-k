"""NX-10 오너 결정 브리프 — **읽기 전용**. “결과를 보고 결정하자”를 실행 가능한 형태로 만든다.

왜 필요한가(2026-09-18 오너 지시): *“일단 해당 부분들은 오늘 오후 모든 테스트가 완료되고 해당 결과를 보고
결정하자.”* 결정 항목 자체는 `docs/ga/GA_OWNER_DECISION_PACKET.md` 가 소유한다(D1~D8 · §4 D-P1~P3 ·
§5 D-F3-1~4). 이 도구는 그 결정들에 **필요한 숫자가 어디 있는지**를 회수 시점에 한 장으로 모은다 —
숫자가 없으면 “없다”고 적는다(없는 근거를 집지 않는다). 그래야 결정 자리에서 문서를 뒤지지 않는다.

무엇을 읽는가(전부 파일·종료 코드):
    · 회수 판정(`soak-recovery-latest.json`) — verdict 와 검사 6건
    · 회수 리포트(마지막 러너 블록이 가리키는 `soak-<초>.json`) — `all_pass`·`missing_required`·SC-6 요약
    · 배치 네 회차의 게이트 리포트(`gate-report-batch-*.json`) — 요약·측정 지문·**빨간 게이트 이름**
    · 처리량 축 키가 리포트에 **생겼는지**(배치 `PERF` 가 적용되면 생긴다) — 있으면 값까지 적는다

이 도구가 **하지 않는 것**: 아무것도 쓰지 않는다. 판정하지 않는다(그건 오너와 대장의 일이다).

사용:
    .venv/bin/python docs/qa/2026-09-16-followup/nx10/batchchain/decision_brief.py
    .venv/bin/python …/decision_brief.py --json
    NX10_STATUS_ROOT=<가짜 트리> …/decision_brief.py     # 시험이 픽스처로 돌린다

종료 코드: 0 = 읽었다(내용이 무엇이든). 1 = 근거 트리를 찾지 못했다.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def _sibling(name: str) -> Any:
    """같은 폴더의 형제 도구를 불러 온다(패키지가 아니다 — 상태판의 규칙을 그대로 쓴다)."""
    spec = importlib.util.spec_from_file_location(f"nx10_{name}", HERE / f"{name}.py")
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PANEL = _sibling("chain_status")

# 처리량 축이 리포트에 나타나면 이런 이름으로 나타난다(배치 `PERF` 가 이 키를 만든다).
THROUGHPUT_HINTS = ("throughput", "efficiency", "utilisation", "utilization", "ops_per", "load1", "baseline")


def _json(path: Path) -> Any:
    text = PANEL.read_text(path)
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return None


# ── 1. 회수 결과(결정의 입력) ────────────────────────────────────────────────────────────────
def recovery(nx10: Path) -> dict[str, Any]:
    verdict = PANEL.last_verdict(nx10)
    block = PANEL.last_soak_block(nx10)
    report_path = Path(block["report"]) if block and block.get("report") else None
    report = _json(report_path) if report_path and report_path.is_file() else None
    soak: dict[str, Any] = {
        "verdict": verdict,
        "block": {
            "start": block.get("start_time"),
            "end": block.get("end_time"),
            "exit": block.get("exit"),
            "attributed": block.get("attributed"),
            "report": str(report_path) if report_path else None,
        }
        if block
        else None,
        "checks": None,
        "report": None,
    }
    recovery_doc = _json(nx10 / "soak-recovery-latest.json")
    if isinstance(recovery_doc, dict):
        checks = recovery_doc.get("checks") or []
        soak["checks"] = {"total": len(checks), "ok": sum(1 for c in checks if c.get("ok"))}
    if isinstance(report, dict):
        scenario = next(
            (s for s in report.get("scenarios") or [] if str(s.get("scenario", "")).startswith("SC-6")), None
        )
        soak["report"] = {
            "all_pass": report.get("all_pass"),
            "missing_required": report.get("missing_required") or [],
            "generated_at": report.get("generated_at"),
            "scenario_count": len(report.get("scenarios") or []),
            "sc6": {
                key: scenario.get(key)
                for key in (
                    "completed_ops",
                    "rss_growth_mb",
                    "errors",
                    "conversation_journal_bytes",
                    "conversation_journal_lines",
                    "conversation_compaction_generations",
                    "duration_s",
                    "pass",
                )
            }
            if scenario
            else None,
        }
        soak["throughput_axis"] = _throughput_axis(report)
    return soak


def _throughput_axis(report: dict[str, Any]) -> dict[str, Any]:
    """리포트에 처리량 축 키가 있으면 값까지, 없으면 없다고 말한다.

    배치 `PERF` 가 적용되면 하네스가 이 축을 리포트에 남긴다 — 그 전에는 정직하게 “없음”이다.
    """
    found: dict[str, Any] = {}
    for scenario in report.get("scenarios") or []:
        if not isinstance(scenario, dict):
            continue
        name = str(scenario.get("scenario", "?"))
        for key, value in scenario.items():
            if any(hint in key.lower() for hint in THROUGHPUT_HINTS):
                found[f"{name}.{key}"] = value
    return {"present": bool(found), "fields": found}


# ── 2. 배치 게이트(네 회차) ─────────────────────────────────────────────────────────────────
def batches(nx10: Path) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for batch in PANEL.BATCHES:
        doc = _json(nx10 / f"gate-report-{batch.gate_label}.json")
        if not isinstance(doc, dict):
            out.append({"batch": batch.name, "present": False})
            continue
        gates = doc.get("gates") or []
        red = [str(g.get("id")) for g in gates if g.get("status") not in ("passed", "skipped")]
        out.append(
            {
                "batch": batch.name,
                "present": True,
                "fingerprint": (doc.get("git") or {}).get("tree_fingerprint"),
                "summary": doc.get("summary") or {},
                "collected": len(gates),
                "red": red,
            }
        )
    return out


# ── 3. 결정 항목과 “필요한 숫자” ───────────────────────────────────────────────────────────────
#   값·선택지의 소유는 `docs/ga/GA_OWNER_DECISION_PACKET.md` 다 — 여기서는 그 결정들이 **어느 숫자를
#   보고 정해지는지**만 적는다. 숫자가 자료에 없으면 “자료 없음”이라고 적는다(지어내지 않는다).
DECISIONS: tuple[tuple[str, str, str], ...] = (
    ("D1", "EX-05 상태 셀 표기(권고 B)", "문서 계약 2건의 red 여부 = 아래 배치 게이트 red 목록"),
    ("D2", "CR-14 후보 재선언(권고 A)", "커밋 뒤 새 SHA·지문 = 아래 배치 지문 네 개"),
    ("D3", "독립 검토자 지정(권고 A)", "숫자가 아니라 조직 — 자료 없음"),
    ("D4", "커밋 승인(3분할)", "무인 체인이 이미 커밋한다 — 커밋 목록은 게이트 리포트의 `git.sha`"),
    ("D5", "값·정책(quota·GC·격리본·flag)", "quota 관측치 — 리포트에 없다(자료 없음)"),
    ("D6", "lexicon 임계·실코퍼스 라벨링", "실사용 회수율 — 미측정(자료 없음)"),
    ("D7", "NX-11 pause·NX-06 kube", "숫자가 아니라 일정 — 자료 없음"),
    ("D8", "soak 판정 규칙·회수 창", "회수 검사 6건(아래 판정)"),
    ("D-P1", "성능 허용 감소 15%", "처리량 분해(효율·이용률) = 아래 처리량 축"),
    ("D-P2", "경합 시 재실행 요구", "같은 축의 `not_applicable` 발생 여부"),
    ("D-P3", "최소 실행 길이 2시간", "실행 길이 = 회수 블록의 `soak_seconds`"),
    ("D-F3-1", "기본 동기화 등급 유지", "비용 모델(핫패스 밖) — 대장 §36 · 이 리포트 밖"),
    ("D-F3-2", "단위·시점 + `T_max` 값", "간섭 실측(밀림·중앙 비용) — 대장 §36 · 이 리포트 밖"),
    ("D-F3-3", "중간 등급(`batched`) 미도입", "이득 2 %p 대 지속성 약속 — 대장 §35 · 이 리포트 밖"),
    ("D-F3-4", "관측 위치(store_usage+로그 1회)", "위 셋과 동거 — 대장 §35 · 이 리포트 밖"),
)


def brief(nx10: Path) -> dict[str, Any]:
    return {"root": str(nx10), "soak": recovery(nx10), "batches": batches(nx10), "decisions": DECISIONS}


def _fmt_axis(axis: dict[str, Any] | None) -> str:
    if axis is None:
        return "자료 없음(회수 리포트를 읽지 못했다)"
    if not axis["present"]:
        return "**자료 없음** — 리포트에 처리량 키가 없다(배치 `PERF` 가 적용되면 생긴다)"
    items = ", ".join(f"{key}={value}" for key, value in list(axis["fields"].items())[:6])
    return items + (f" … 외 {len(axis['fields']) - 6}개" if len(axis["fields"]) > 6 else "")


def render(state: dict[str, Any]) -> str:
    lines: list[str] = []
    soak = state["soak"]
    verdict = soak.get("verdict") or {}
    lines.append("=== 회수 결과 (결정의 입력) ===")
    block = soak.get("block") or {}
    checks = soak.get("checks") or {}
    lines.append(
        f"  판정: {verdict.get('verdict') or '(없음)'} · 검사 {checks.get('ok', '?')}/{checks.get('total', '?')}"
        f" · 수집 {verdict.get('collected_at') or '?'}"
    )
    lines.append(
        f"  실행 블록: {block.get('start')} → {block.get('end') or '실행 중'} · exit {block.get('exit')}"
        f" · 지문 {'일치' if block.get('attributed') else '**갈렸다**'}"
    )
    report = soak.get("report")
    if report:
        sc6 = report.get("sc6") or {}
        lines.append(
            f"  리포트: all_pass={report.get('all_pass')} · missing_required={report.get('missing_required')}"
            f" · 시나리오 {report.get('scenario_count')}개"
        )
        lines.append(
            f"  SC-6: 완료 {sc6.get('completed_ops')} ops · RSS 증가 {sc6.get('rss_growth_mb')} MB"
            f" · 오류 {sc6.get('errors')} · 저널 {sc6.get('conversation_journal_lines')} 줄"
            f" · pass={sc6.get('pass')}"
        )
    else:
        lines.append("  리포트: 못 읽었다")
    lines.append(f"  처리량 축: {_fmt_axis(soak.get('throughput_axis'))}")

    lines.append("")
    lines.append("=== 배치 게이트 (네 회차 · 빨간 이름이 결정의 증거다) ===")
    for batch in state["batches"]:
        if not batch["present"]:
            lines.append(f"  [{batch['batch']}] 게이트 리포트 없음")
            continue
        summary = batch["summary"]
        red = ", ".join(batch["red"]) or "없음"
        fp = (batch["fingerprint"] or "?")[:12]
        lines.append(
            f"  [{batch['batch']}] 지문 {fp}… · {summary.get('passed')} passed · {summary.get('failed')} failed"
            f" · {summary.get('not_run', 0)} not_run(수집 {batch['collected']}/23) · red: {red}"
        )

    lines.append("")
    lines.append("=== 결정 대장 (무엇을 정하는가 — 필요한 숫자) ===")
    for ident, question, evidence in state["decisions"]:
        lines.append(f"  {ident:7s} {question} — {evidence}")

    lines.append("")
    lines.append("=== 다음 할 일 ===")
    lines.append("  결과를 먼저 보고하고, 그 다음 결정을 청한다(순서를 뒤집지 않는다).")
    lines.append("  숫자가 ‘자료 없음’인 항목은 결정 전에 그 숫자를 만드는 배치가 필요하다는 뜻이다.")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="NX-10 오너 결정 브리프(읽기 전용)")
    parser.add_argument("--json", action="store_true", help="기계 판독 JSON")
    parser.add_argument("--root", default=os.environ.get("NX10_STATUS_ROOT") or str(HERE.parent))
    args = parser.parse_args(argv)
    root = Path(args.root).resolve()
    if not root.is_dir():
        print(f"[FAIL] 근거 트리가 없다: {root}", file=sys.stderr)
        return 1
    state = brief(root)
    print(json.dumps(state, ensure_ascii=False, indent=2, default=str) if args.json else render(state))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
