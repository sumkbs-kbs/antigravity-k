#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pydantic>=2.10.0,<3.0", "typer>=0.13.0,<1.0"]
# ///
# ─── How to run ───
# uv run scripts/run_attempt_close.py --attempt attempt-017 --stage fast
# uv run scripts/run_attempt_close.py --attempt attempt-017 --stage tests
# uv run scripts/run_attempt_close.py --attempt attempt-017 --stage heavy
# uv run scripts/run_attempt_close.py --attempt attempt-017 --stage close   # 보고서 편입 + 마감 검사
#   (한 번에 돌리려면 --stage all. 게이트 21개 전체는 10분 이상 걸린다.)
#
# exit code: 0 = 마감 가능, 1 = gate 실패 또는 마감 검사 FAIL, 2 = 사용/파일 오류
#   (보고서가 **다른 코드 상태**의 것이라 이어받을 수 없을 때도 2 다 — 조용히 새로 시작하지 않는다: F-27).

"""attempt 마감 **절차** — 게이트 → 보고서 편입 → 마감 검사 → 기록 확인 (CR-14 R-10).

왜 필요한가
===========
attempt-016 은 "선언한 초록의 출처"를 확인하는 마감 검사(`verify_attempt_close.py`)를 만들고,
그것이 **사람이(또는 절차가) 돌려야** 작동한다는 사실을 한계 R-10 으로 남겼다. 한계 목록의
문장은 다음 사람이 다시 잊게 만든다 — 이 스크립트가 그 문장을 **명령 하나**로 바꾼다.

순서 (attempt-016 이 실측으로 확인한 순서다)
============================================
  1. 코드 후보를 커밋하고, 판정 카드에 후보 SHA·지문을 **선언한 뒤** (D-52)
  2. `--stage fast` → 빠른 게이트 18개
  3. `--stage tests` → `python-tests`(약 9분)
  4. `--stage heavy` → `docker-build` · `clean-machine-runtime`(약 6분)
  5. `--stage close` → `.artifacts/` 의 보고서를 증거 트리(`attempt-0NN/gate-report.json`)에
     **편입**하고 마감 검사를 돌린다 — 이 단계가 있어야 "선언한 초록의 출처"가 생긴다
  6. 기록 커밋(`docs/` 전용) 뒤 **다시 `--stage close`** 로 지문 불변을 확인한다

게이트 목록은 **manifest 에서 읽는다**(스크립트에 개수를 박지 않는다 — F-21 이 개수 고정을
목록 고정으로 바꾼 이유와 같다). `heavy` 로 분류된 세 개만 배치 경계를 위해 이름으로 지정하고,
나머지는 전부 `fast` 로 간다: manifest 에 게이트를 추가하면 **빠짐없이 fast 에 들어간다**.

이어받기(F-26·F-27)
==================
각 `--stage` 는 **별개 프로세스**다 — 그 안에서는 "내가 첫 배치인가"를 알 수 없다. 그래서
판단 근거는 프로세스 기억이 아니라 **보고서 파일의 정체성**이다. 그 정체성의 정의는 이
스크립트가 아니라 **게이트**(`ga_gate.merge_refusal_reason`: 후보 sha · manifest · 작업 트리
지문)가 소유하고, 여기서는 **묻기만** 한다 — 복제하면 두 주체가 갈라진다(F-27: 절차는 두
축만 보았고, 그래서 게이트가 거부하는 조합을 "이어받는다"고 판단해 실행이 중단됐다).
거부되는 조합에서는 **조용히 새로 시작하지 않고 이유를 대며 끊는다**(exit 2).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import shutil
import subprocess
import sys
from collections.abc import Sequence
from pathlib import Path
from types import ModuleType
from typing import Any, Final, cast

_REPO_ROOT = Path(__file__).resolve().parents[1]
_GATE_SCRIPT = _REPO_ROOT / "scripts" / "ga_gate.py"
_CLOSER_SCRIPT = _REPO_ROOT / "scripts" / "verify_attempt_close.py"
_DEFAULT_MANIFEST = Path("scripts/commercial_ga_gates.json")
_DEFAULT_CARD = Path("docs/ga/CR14_FINAL_CANDIDATE_VERDICT.md")
_DEFAULT_EVIDENCE_ROOT = Path(".omo/evidence/commercial-reliability/CR-14")

# 배치 경계를 만드는 세 게이트 — 오래 걸리거나(테스트·도커) 별도 아티팩트를 만든다(clean-machine).
# **개수가 아니라 이름**으로 지정한다: 나머지는 manifest 가 정한다.
HEAVY_STAGES: Final[dict[str, tuple[str, ...]]] = {
    "tests": ("python-tests",),
    "heavy": ("docker-build", "clean-machine-runtime"),
}
_STAGE_ORDER: Final = ("fast", "tests", "heavy", "close")


class UsageError(Exception):
    """입력·배치가 성립하지 않는다(판정 FAIL 이 아니라 사용 오류)."""


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:  # pragma: no cover - 배포 형태가 깨진 경우
        raise UsageError(f"스크립트를 불러올 수 없다: {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass 를 쓰는 모듈은 sys.modules 등록이 필요하다
    spec.loader.exec_module(module)
    return module


_CLOSER = _load(_CLOSER_SCRIPT, "attempt_close_verifier")
# 이어받기 **규칙**은 게이트가 소유한다 — 절차는 그 함수를 **묻기만** 한다(F-27).
_GATE = _load(_GATE_SCRIPT, "attempt_close_procedure_ga_gate")


def required_gate_ids(manifest: dict[str, Any]) -> list[str]:
    """manifest 의 required gate id — 순서는 manifest 가 정한다."""
    return [str(gate.get("id")) for gate in (manifest.get("gates") or []) if gate.get("required")]


def plan_stage(stage: str, gate_ids: Sequence[str]) -> list[str]:
    """배치가 돌릴 gate id 목록(순수 함수 — manifest 를 받아 계산한다).

    `fast` 는 **required 전체에서 무거운 셋을 뺀 나머지**다. 그래서 manifest 에 게이트를
    추가하면 자동으로 fast 에 들어가고, 개수를 손으로 맞출 일이 없다(F-21 의 교훈).
    """
    if stage == "close":
        return []
    if stage == "fast":
        heavy = {gate_id for ids in HEAVY_STAGES.values() for gate_id in ids}
        return [gate_id for gate_id in gate_ids if gate_id not in heavy]
    if stage in HEAVY_STAGES:
        wanted = set(HEAVY_STAGES[stage])
        unknown = sorted(wanted - set(gate_ids))
        if unknown:
            raise UsageError(f"`{stage}` 배치의 gate 가 manifest 에 없다: {unknown}")
        return [gate_id for gate_id in gate_ids if gate_id in wanted]
    raise UsageError(f"알 수 없는 단계다: {stage} (가능: {', '.join((*_STAGE_ORDER, 'all'))})")


def gate_command(  # noqa: PLR0913 — argv 한 벌을 만드는 함수라 인자가 많다
    gate_ids: Sequence[str], *, manifest: Path, output: Path, merge_into: bool, repo_root: Path
) -> list[str]:
    """`ga_gate.py` 호출 argv — 배치 경계마다 `--merge-into` 를 붙이는 규칙을 여기서만 정한다."""
    command = [
        "uv",
        "run",
        "--no-sync",
        "python",
        str(repo_root / "scripts" / "ga_gate.py"),  # --repo-root 안의 게이트 실행자를 돌린다
        "--manifest",
        str(manifest),
        "--output",
        str(output),
    ]
    for gate_id in gate_ids:
        command += ["--only", gate_id]
    if merge_into:
        command.append("--merge-into")
    return command


def merge_identity(repo_root: Path, manifest_path: Path) -> tuple[str, str, str]:
    """이어받기 판단에 넘길 **세 축** — 게이트가 보고서에 적는 것과 **같은 값**이다.

    지문은 게이트의 `worktree_fingerprint` 를 그대로 쓴다. 절차가 지문을 따로 계산하면
    규칙이 갈라진다(F-27 · attempt-016 이 `tree_fingerprint_of_commit` 을 한 곳으로 올린 것과
    같은 이유).
    """
    fingerprint = str(_GATE.worktree_fingerprint(repo_root))
    return _head(repo_root), _manifest_sha256(manifest_path), fingerprint


def merge_decision(output: Path, *, sha: str, manifest_sha: str, tree_fingerprint: str) -> str:
    """이 배치가 이어받을지 — `"fresh"`(보고서 없음) · `"merge"` · 또는 **거부 이유**.

    **규칙을 복제하지 않는다** — 게이트가 쓰는 `merge_refusal_reason` 을 그대로 묻는다.
    attempt-017 의 첫 구현은 `(후보 sha, manifest sha256)` 만 보는 **부분 복제**였고, 게이트는
    **작업 트리 지문**까지 보기 때문에 두 주체가 갈라졌다(F-27): 절차가 "이어받는다"고 판단한
    조합을 게이트가 거부해 `--merge-into` 가 실행을 exit 2 로 끊었다.

    거부를 **조용히 새 시작으로 바꾸지 않는** 것이 나머지 절반이다. 앞 배치의 초록을 버리는
    경로가 조용하면 아무도 모른다 — F-26 이 한 조용한 경로를 닫았고, 이것이 남은 경로다.
    새로 시작하려는 사람은 보고서를 **명시적으로 지우게** 한다.
    """
    if not output.is_file():
        return "fresh"
    reason = _GATE.merge_refusal_reason(output, sha, manifest_sha, tree_fingerprint)
    return "merge" if reason is None else str(reason)


def file_report(source: Path, attempt_dir: Path) -> Path:
    """`.artifacts/` 의 보고서를 증거 트리에 **편입**한다 — 마감의 마지막 한 걸음.

    내용이 JSON 이 아니면 편입하지 않는다(깨진 보고서를 증거로 만들지 않는다).
    """
    if not source.is_file():
        raise UsageError(f"보고서가 없다: {source} — 먼저 게이트를 돌려야 한다")
    try:
        json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise UsageError(f"보고서를 JSON 으로 읽을 수 없다: {source} ({error})") from error
    attempt_dir.mkdir(parents=True, exist_ok=True)
    target = attempt_dir / "gate-report.json"
    shutil.copy2(source, target)
    return target


def _run_stage(
    stage: str, ids: Sequence[str], *, manifest: Path, output: Path, merge_into: bool, repo_root: Path
) -> int:
    command = gate_command(ids, manifest=manifest, output=output, merge_into=merge_into, repo_root=repo_root)
    print(f"[{stage}] {' '.join(command)}", flush=True)
    result = subprocess.run(command, cwd=repo_root, check=False)
    return result.returncode


def _head(repo_root: Path) -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo_root, capture_output=True, check=False, text=True)
    if result.returncode != 0:
        raise UsageError("HEAD 를 읽을 수 없다 — git 저장소에서 실행해야 한다")
    return result.stdout.strip()


def _manifest_sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()


def _close(*, card: Path, evidence_root: Path, manifest: Path, repo_root: Path, attempt: str) -> int:
    attempt_dir = evidence_root / attempt
    try:
        target = file_report(Path(_artifacts_output(attempt, repo_root)), attempt_dir)
    except UsageError as error:
        print(f"ERROR {error}", file=sys.stderr)
        return 2
    print(f"[close] 보고서 편입: {target}")
    try:
        card_text = card.read_text(encoding="utf-8")
    except OSError as error:
        # 사용 오류는 exit 2 라는 관례가 여기서만 깨져 있었다(읽을 수 없는 카드 → traceback).
        print(f"ERROR 카드를 읽을 수 없다: {card} ({error})", file=sys.stderr)
        return 2
    try:
        problems = cast(
            "list[str]",
            _CLOSER.close_violations(
                card_text=card_text, repo_root=repo_root, evidence_root=evidence_root, manifest_path=manifest
            ),
        )
    except Exception as error:  # UsageError 를 포함해 사용 오류는 exit 2 로 구분한다
        print(f"ERROR {error}", file=sys.stderr)
        return 2
    for problem in problems:
        print(f"FAIL  {problem}")
    if problems:
        print(f"[close] ATTEMPT_CLOSE: FAIL ({len(problems)}건)")
        return 1
    print("[close] ATTEMPT_CLOSE: PASS — 선언한 초록이 증거 파일로 뒷받침된다")
    return 0


def _artifacts_output(attempt: str, repo_root: Path) -> str:
    return str(repo_root / ".artifacts" / f"commercial-ga-{attempt.replace('attempt-', '')}-close.json")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CR-14 attempt 마감 절차 (R-10).")
    parser.add_argument("--attempt", required=True, help="증거 디렉터리 이름(예: attempt-017)")
    parser.add_argument("--stage", required=True, choices=[*_STAGE_ORDER, "all"])
    parser.add_argument("--manifest", type=Path, default=_DEFAULT_MANIFEST)
    parser.add_argument("--card", type=Path, default=_DEFAULT_CARD)
    parser.add_argument("--evidence-root", type=Path, default=_DEFAULT_EVIDENCE_ROOT)
    parser.add_argument("--repo-root", type=Path, default=Path("."))
    args = parser.parse_args(argv)

    repo_root = args.repo_root.resolve()
    manifest_path = (repo_root / args.manifest).resolve() if not args.manifest.is_absolute() else args.manifest
    card_path = (repo_root / args.card).resolve() if not args.card.is_absolute() else args.card
    evidence_root = (
        (repo_root / args.evidence_root).resolve() if not args.evidence_root.is_absolute() else args.evidence_root
    )
    output = Path(_artifacts_output(args.attempt, repo_root))

    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        print(f"ERROR manifest 를 읽을 수 없다: {manifest_path} ({error})", file=sys.stderr)
        return 2
    gate_ids = required_gate_ids(manifest)
    if not gate_ids:
        print(f"ERROR manifest 에 required gate 가 없다: {manifest_path}", file=sys.stderr)
        return 2

    stages = list(_STAGE_ORDER) if args.stage == "all" else [args.stage]
    # 이어받기는 **보고서의 정체성**으로 결정한다 — 그리고 그 정체성의 정의는 게이트가 소유한다
    # (`merge_refusal_reason`: 후보 sha · manifest · 작업 트리 지문). 복제하면 갈라진다(F-27).
    # `close` 는 게이트를 돌리지 않으므로 판단이 필요 없다 — 기록 커밋 뒤의 재확인을 막지 않는다.
    merge_into = False
    if any(stage != "close" for stage in stages):
        try:
            sha, manifest_sha, tree_fingerprint = merge_identity(repo_root, manifest_path)
        except UsageError as error:
            print(f"ERROR {error}", file=sys.stderr)
            return 2
        decision = merge_decision(output, sha=sha, manifest_sha=manifest_sha, tree_fingerprint=tree_fingerprint)
        if decision == "fresh":
            print(f"[merge] 새 보고서로 시작한다 ({output})")
        elif decision == "merge":
            merge_into = True
            print(f"[merge] 이어받는다 ({output})")
        else:
            print(f"ERROR 이어받을 수 없다: {decision}", file=sys.stderr)
            print(
                f"      앞 배치의 초록을 버리고 새로 시작하려면 보고서를 지우고 다시 실행하라: rm {output}",
                file=sys.stderr,
            )
            return 2
    else:
        print("[merge] close 단계는 게이트를 돌리지 않는다 — 이어받기 판단이 필요 없다")
    for stage in stages:
        if stage == "close":
            return _close(
                card=card_path,
                evidence_root=evidence_root,
                manifest=manifest_path,
                repo_root=repo_root,
                attempt=args.attempt,
            )
        try:
            ids = plan_stage(stage, gate_ids)
        except UsageError as error:
            print(f"ERROR {error}", file=sys.stderr)
            return 2
        if not ids:
            continue
        code = _run_stage(
            stage,
            ids,
            manifest=manifest_path,
            output=output,
            merge_into=merge_into,
            repo_root=repo_root,
        )
        print(f"[{stage}] {len(ids)}개 gate 실행 완료 — exit {code}")
        if code != 0:
            print(f"ERROR 게이트 실행이 실패했다({stage}, exit {code})", file=sys.stderr)
            return 1
        merge_into = True
    print("[all] 게이트 배치가 끝났다 — `--stage close` 로 보고서 편입과 마감 검사를 돌린다")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
