#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.10.0,<3.0", "typer>=0.13.0,<1.0"]
# ///
# ─── How to run ───
# uv run scripts/verify_attempt_close.py \
#   --card docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md \
#   --evidence-root .omo/evidence/commercial-reliability/CR-14 \
#   --manifest scripts/commercial_ga_gates.json
#
# exit code: 0 = 마감 가능, 1 = 판정 FAIL, 2 = 사용/파일 오류.

"""attempt **마감 검사** — "선언한 초록"이 실제로 존재하는가(CR-14 R-9).

왜 게이트가 아닌가
==================
`tests/test_cr14_fence_movement_detection.py`(C14-F23)는 "보고서가 **있으면** 그 보고서가
자기가 이름 붙인 트리를 측정했는가"를 본다. 그 계약은 **보고서의 존재**를 요구할 수 없다:
보고서는 게이트 실행이 끝날 때 쓰이므로, 그 실행 **안에서는** 존재할 수 없다(순환).
그래서 required gate 21개를 전부 통과한 뒤에도 "카드가 선언한 지문을 측정한 보고서가 실제로
있는가"를 묻는 자리가 비어 있었다 — attempt-013 의 21/21 이 HEAD 가 아닌 트리를 가리키게 됐을 때
아무도 묻지 않은 것도 같은 구멍이다.

이 검사는 그 구멍을 **게이트 밖에서** 닫는다. 게이트 실행이 끝난 뒤(= 보고서가 쓰인 뒤) 한 번
돌려서, 카드의 주장과 증거 파일이 서로를 지지하는지 확인한다.

검사 항목
=========
  1. 카드의 선언 자리 — 후보 SHA(40hex) · 코드 지문(64hex) · 게이트 수치(4개)가 **각각 하나**.
  2. **선언된 지문을 측정한 보고서가 있는가** (R-9 의 핵심).
  3. 그 보고서가 이름 붙인 커밋의 **코드 트리 == 보고서의 지문** (다른 트리를 재고 sha 만 적은
     보고서 거부 — 커밋 뒤에 코드가 움직였으면 여기서도 걸린다).
  4. 보고서의 `manifest.sha256` == 현재 manifest 파일의 sha256, required gate **목록**이
     manifest 와 같은가(개수만 맞추는 경로 차단).
  5. required gate 전부 `passed` · `exit_code == 0`, 그리고 같은 지문에 실패한 실행이 없다.
  6. 카드의 `inventory / PASS / FAIL / NOT_RUN` 수치가 보고서 집계와 **같은가**(손으로 적은 수치 금지).
  7. 후보..HEAD 사이에 **코드 스코프 변경이 없는가**(기록 커밋이 지문을 옮기지 않았다).

이 검사는 gate inventory 에 **넣지 않는다** — 넣으면 순환이 생겨 영원히 실패한다(위 주석 참조).
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import subprocess
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Any, cast

_SHA_LENGTH = 40
_FINGERPRINT_LENGTH = 64
_DEFAULT_CARD = Path("docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md")
_DEFAULT_EVIDENCE_ROOT = Path(".omo/evidence/commercial-reliability/CR-14")
_DEFAULT_MANIFEST = Path("scripts/commercial_ga_gates.json")
_GATE_SCRIPT = Path(__file__).resolve().parent / "ga_gate.py"
# 보고서 발견 규칙 — **여기가 유일한 자리**다. 파이프라인(.github/workflows/ga-close.yml)이
# 넘기는 시도 이름도 이 글로브에 맞아야 한다(계약 `tests/test_cr14_close_pipeline_contract.py`
# 가 그 정합을 소유자의 상수에서 직접 읽어 확인한다).
REPORT_GLOB = "attempt-*/gate-report.json"

# 판정 카드는 값의 **유일한** 선언 자리다(C14-F15-2). 각 패턴이 정확히 하나씩만 맞아야 한다.
_CANDIDATE_RE = re.compile(r"code candidate full SHA: \*\*`([0-9a-f]{40})`\*\*")
_FINGERPRINT_RE = re.compile(r"코드 지문 \*\*`([0-9a-f]{64})`\*\*")
_GATE_NUMBERS_RE = re.compile(r"required gate inventory / PASS / FAIL / NOT_RUN: \*\*(\d+) / (\d+) / (\d+) / (\d+)\*\*")


class UsageError(Exception):
    """입력·선언 자리가 성립하지 않는다(판정 FAIL 이 아니라 **사용 오류**)."""


@dataclass(frozen=True)
class Declaration:
    """판정 카드가 선언한 것 — 후보·지문·게이트 수치."""

    candidate: str
    fingerprint: str
    inventory: int
    passed: int
    failed: int
    not_run: int


def _load_gate_module() -> ModuleType:
    spec = importlib.util.spec_from_file_location("attempt_close_ga_gate", _GATE_SCRIPT)
    if spec is None or spec.loader is None:  # pragma: no cover - 배포 형태가 깨진 경우
        raise UsageError(f"gate 스크립트를 불러올 수 없다: {_GATE_SCRIPT}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


_GATE = _load_gate_module()
# 지문 규칙은 **게이트가 실제로 쓰는** 함수에서 온다 — 여기서 다시 구현하면 규칙이 갈라진다.
tree_fingerprint_of_commit = cast(
    "Callable[[Path, str, Sequence[str] | None], str]", getattr(_GATE, "tree_fingerprint_of_commit")
)
code_scope_changes = cast(
    "Callable[[Path, str, str, Sequence[str] | None], list[str]]", getattr(_GATE, "code_scope_changes")
)


def parse_declaration(card_text: str) -> Declaration:
    """카드의 선언을 읽는다. 각 자리가 정확히 하나가 아니면 `UsageError`."""
    candidates = _CANDIDATE_RE.findall(card_text)
    fingerprints = _FINGERPRINT_RE.findall(card_text)
    numbers = _GATE_NUMBERS_RE.findall(card_text)
    if len(candidates) != 1 or len(fingerprints) != 1 or len(numbers) != 1:
        raise UsageError(
            "선언 자리가 각각 하나여야 한다 — "
            f"후보 {len(candidates)}개 · 지문 {len(fingerprints)}개 · 게이트 수치 {len(numbers)}개"
        )
    inventory, passed, failed, not_run = (int(value) for value in numbers[0])
    return Declaration(
        candidate=candidates[0],
        fingerprint=fingerprints[0],
        inventory=inventory,
        passed=passed,
        failed=failed,
        not_run=not_run,
    )


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, capture_output=True, check=False)
    if result.returncode != 0:
        return ""
    return result.stdout.decode("utf-8", "replace").strip()


def _has_commit(root: Path, revision: str) -> bool:
    """`git cat-file -e` 는 성공해도 아무것도 출력하지 않는다 — 종료코드로 판정해야 한다."""
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return cast("dict[str, Any]", json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report_sort_key(report: dict[str, Any]) -> str:
    return str(report.get("generated_at") or "")


def _required_ids(payload: dict[str, Any]) -> list[str]:
    gates = payload.get("gates") or []
    return sorted(str(gate.get("id")) for gate in gates if gate.get("required"))


def close_violations(
    *,
    card_text: str,
    repo_root: Path,
    evidence_root: Path,
    manifest_path: Path,
) -> list[str]:
    """마감을 막는 사유 목록(빈 목록 = 마감 가능). 사용 오류는 `UsageError` 로 올린다."""
    declared = parse_declaration(card_text)
    problems: list[str] = []

    if not _has_commit(repo_root, declared.candidate):
        raise UsageError(f"선언된 후보 커밋이 이 저장소에 없다: {declared.candidate}")
    if not manifest_path.is_file():
        raise UsageError(f"manifest 를 찾을 수 없다: {manifest_path}")
    manifest = _read_json(manifest_path)
    if manifest is None:
        raise UsageError(f"manifest 를 읽을 수 없다: {manifest_path}")

    # (2) 선언된 지문을 측정한 보고서가 있는가 — R-9 의 핵심.
    reports: list[tuple[Path, dict[str, Any]]] = []
    for path in sorted(evidence_root.glob(REPORT_GLOB)):
        payload = _read_json(path)
        if payload is None:
            problems.append(f"{path.parent.name}: 보고서를 읽을 수 없다(손상되었거나 JSON 이 아니다)")
            continue
        if (payload.get("git") or {}).get("tree_fingerprint") == declared.fingerprint:
            reports.append((path, payload))
    if not reports:
        problems.append(
            "evidence: 선언된 지문을 측정한 gate 보고서가 없다 — 카드가 주장하는 초록의 출처가 없다"
            f"(지문 {declared.fingerprint[:16]}…, 찾은 곳 {evidence_root})"
        )

    # (3) 보고서가 이름 붙인 커밋의 코드 트리 == 보고서의 지문.
    for path, payload in reports:
        label = path.parent.name
        git = payload.get("git") or {}
        sha = str(git.get("sha") or "")
        if not sha or not _has_commit(repo_root, sha):
            problems.append(f"{label}: 보고서가 이름 붙인 커밋 {sha or '(없음)'} 을 이 저장소에서 찾을 수 없다")
            continue
        if tree_fingerprint_of_commit(repo_root, sha, None) != declared.fingerprint:
            problems.append(
                f"{label}: 보고서 지문이 이름 붙인 커밋 {sha[:12]} 의 코드 트리와 다르다 "
                "— 커밋되지 않은 트리를 쟀거나, 측정 뒤에 그 커밋의 코드가 움직였다"
            )
        required_failed = [
            str(gate.get("id"))
            for gate in (payload.get("gates") or [])
            if gate.get("required") and gate.get("status") != "passed"
        ]
        if required_failed:
            problems.append(f"{label}: 같은 지문에 required gate 실패가 있다 {required_failed} — 증거가 섞였다")

    # (4)(5)(6) 최신 보고서와 카드·manifest 를 대조한다.
    if reports:
        latest_path, latest = max(reports, key=lambda item: _report_sort_key(item[1]))
        label = latest_path.parent.name
        manifest_sha = _file_sha256(manifest_path)
        reported_manifest = str((latest.get("manifest") or {}).get("sha256") or "")
        if reported_manifest != manifest_sha:
            problems.append(
                f"{label}: 보고서의 manifest sha256({reported_manifest[:16]}…)이 현재 "
                f"manifest 와 다르다({manifest_sha[:16]}…) — 게이트 목록이 바뀐 뒤 재측정하지 않았다"
            )
        expected_ids = _required_ids(manifest)
        reported_ids = _required_ids(latest)
        if reported_ids != expected_ids:
            missing = sorted(set(expected_ids) - set(reported_ids))
            extra = sorted(set(reported_ids) - set(expected_ids))
            problems.append(f"{label}: required gate 목록이 manifest 와 다르다 — 빠짐 {missing} · 추가 {extra}")
        gates = latest.get("gates") or []
        not_passed = [str(gate.get("id")) for gate in gates if gate.get("status") != "passed"]
        bad_exit = [str(gate.get("id")) for gate in gates if gate.get("exit_code") != 0]
        if not_passed:
            problems.append(f"{label}: PASS 가 아닌 gate 가 있다 {not_passed}")
        if bad_exit:
            problems.append(f"{label}: exit_code 가 0 이 아닌 gate 가 있다 {bad_exit}")
        required_gates = [gate for gate in gates if gate.get("required")]
        observed = {
            "inventory": len(required_gates),
            "passed": sum(1 for gate in required_gates if gate.get("status") == "passed"),
            "failed": sum(1 for gate in required_gates if gate.get("status") == "failed"),
            "not_run": sum(1 for gate in required_gates if gate.get("status") not in {"passed", "failed"}),
        }
        claimed = {
            "inventory": declared.inventory,
            "passed": declared.passed,
            "failed": declared.failed,
            "not_run": declared.not_run,
        }
        if claimed != observed:
            problems.append(
                f"card: 선언한 게이트 수치 {claimed} 가 보고서 집계 {observed} 와 다르다 "
                f"({label}) — 수치는 손으로 적지 않고 측정에서 온다"
            )
        # 보고서 summary 의 정의는 `ga_gate._summary` 와 같아야 한다:
        # `failed = 전체 − passed` · `required_failed = required 중 passed 가 아닌 것` · `total = 전체`.
        summary = latest.get("summary") or {}
        passed_all = sum(1 for gate in gates if gate.get("status") == "passed")
        expected_summary = {
            "total": len(gates),
            "passed": passed_all,
            "failed": len(gates) - passed_all,
            "required_failed": sum(1 for gate in required_gates if gate.get("status") != "passed"),
        }
        reported_summary = {
            "total": summary.get("total"),
            "passed": summary.get("passed"),
            "failed": summary.get("failed"),
            "required_failed": summary.get("required_failed"),
        }
        if reported_summary != expected_summary:
            problems.append(
                f"{label}: 보고서 summary {reported_summary} 가 gate 목록 집계 {expected_summary} 와 다르다"
            )

    # (7) 울타리 — 후보..HEAD 에 코드 스코프 변경이 없어야 한다.
    head = _git(repo_root, "rev-parse", "HEAD")
    if not head:
        raise UsageError("HEAD 를 읽을 수 없다 — git 저장소에서 실행해야 한다")
    moved = code_scope_changes(repo_root, declared.candidate, head, None)
    if moved:
        problems.append(f"fence: 후보 뒤에 코드 스코프가 움직였다 — 그 커밋들의 초록은 이 후보의 것이 아니다: {moved}")
    return problems


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="CR-14 attempt 마감 검사 — 선언한 초록이 실제로 존재하는가(R-9).",
    )
    parser.add_argument("--card", type=Path, default=_DEFAULT_CARD)
    parser.add_argument("--evidence-root", type=Path, default=_DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    parser.add_argument("--json", action="store_true", help="결과를 JSON 한 줄로 낸다")
    args = parser.parse_args(argv)

    try:
        card_text = args.card.read_text(encoding="utf-8")
    except OSError as error:
        print(f"FAIL  card: 판정 카드를 읽을 수 없다 ({error})", file=sys.stderr)
        return 2

    try:
        problems = close_violations(
            card_text=card_text,
            repo_root=args.repo_root,
            evidence_root=args.evidence_root,
            manifest_path=args.manifest,
        )
    except UsageError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps({"verdict": "FAIL" if problems else "PASS", "problems": problems}, ensure_ascii=False))
    else:
        for problem in problems:
            print(f"FAIL  {problem}")
        if problems:
            print(f"\nATTEMPT_CLOSE: FAIL ({len(problems)}건)")
        else:
            print("ATTEMPT_CLOSE: PASS — 선언한 초록이 증거 파일로 뒷받침된다")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
