"""CR-14 — **마감 절차**(`scripts/run_attempt_close.py`)와 그 이빨 (R-10).

attempt-016 은 마감 검사를 만들고 "사람이(또는 절차가) 돌려야 작동한다"를 한계 R-10 으로 남겼다.
이 파일은 그 절차가 **게이트 목록을 manifest 에서 읽고**, 배치 경계마다 `--merge-into` 를 붙이고,
보고서를 증거 트리에 **편입한 뒤에만** 마감 검사를 통과시키는지를 고정한다.

왜 이빨이 필요한가: 절차가 게이트 목록을 **스스로 들고 있으면**(개수·이름을 하드코딩하면) manifest 에
게이트를 추가해도 그 게이트는 돌지 않는다 — 검사를 빼는 경로가 조용히 열린다(F-21 이 개수 고정을
목록 고정으로 바꾼 이유, C14-01c 이 인벤토리를 못 박은 이유와 같은 병). 그래서 배치 계획을
**순수 함수**(`plan_stage(stage, gate_ids)`)로 두고, 임의의 목록을 넣어 확인한다.

이 파일은 실제 게이트를 돌리지 않는다(10분이 걸린다) — 그 부분은 attempt-019 실측이 증거다.
"""

from __future__ import annotations

import importlib.util
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_PROCEDURE_SCRIPT = REPO_ROOT / "scripts" / "run_attempt_close.py"
_MANIFEST = REPO_ROOT / "scripts" / "commercial_ga_gates.json"


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass 를 쓰는 모듈은 등록이 필요하다
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def procedure() -> ModuleType:
    return _load(_PROCEDURE_SCRIPT, "cr14_attempt_close_procedure_under_test")


@pytest.fixture(scope="module")
def manifest_ids(procedure: ModuleType) -> list[str]:
    manifest = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    reader = procedure.required_gate_ids
    assert isinstance(reader, Callable)
    return list(reader(manifest))


# ---------------------------------------------------------------------------
# 계약 — 배치가 게이트를 **빠뜨리지 않는다**
# ---------------------------------------------------------------------------


def test_three_gate_stages_partition_the_manifest_without_loss(procedure: ModuleType, manifest_ids: list[str]) -> None:
    """세 배치의 합집합 == manifest 의 required 전부(빠짐·중복 없음)."""
    plan = procedure.plan_stage
    assert isinstance(plan, Callable)
    staged: list[str] = []
    for stage in ("fast", "tests", "heavy"):
        staged += list(plan(stage, manifest_ids))
    assert sorted(staged) == sorted(manifest_ids)
    assert len(staged) == len(set(staged)), "같은 gate 가 두 배치에 들어갔다"


def test_fast_stage_is_derived_not_hardcoded(procedure: ModuleType) -> None:
    """`fast` 는 **무거운 셋을 뺀 나머지**다 — manifest 에 게이트를 추가하면 자동으로 fast 에 온다."""
    plan = procedure.plan_stage
    assert isinstance(plan, Callable)
    synthetic = ["alpha", "beta", "python-tests", "docker-build", "clean-machine-runtime", "gamma"]
    assert list(plan("fast", synthetic)) == ["alpha", "beta", "gamma"]
    assert list(plan("tests", synthetic)) == ["python-tests"]
    assert list(plan("heavy", synthetic)) == ["docker-build", "clean-machine-runtime"]
    assert list(plan("close", synthetic)) == []


def test_close_stage_runs_no_gate(procedure: ModuleType, manifest_ids: list[str]) -> None:
    """마감 단계는 게이트를 돌리지 않는다 — 돌리면 보고서가 다시 쓰여 '측정된 초록'이 흔들린다."""
    plan = procedure.plan_stage
    assert isinstance(plan, Callable)
    assert list(plan("close", manifest_ids)) == []


def test_unknown_stage_and_missing_gate_are_usage_errors(procedure: ModuleType) -> None:
    plan = procedure.plan_stage
    assert isinstance(plan, Callable)
    with pytest.raises(procedure.UsageError):
        plan("느린단계", ["a"])
    with pytest.raises(procedure.UsageError):
        plan("heavy", ["python-tests"])  # docker-build 가 없는 manifest


def test_gate_command_carries_exactly_the_stage_gates(procedure: ModuleType) -> None:
    builder = procedure.gate_command
    assert isinstance(builder, Callable)
    command = list(
        builder(
            ["alpha", "beta"],
            manifest=Path("scripts/commercial_ga_gates.json"),
            output=Path(".artifacts/x.json"),
            merge_into=True,
            repo_root=Path("."),
        )
    )
    assert command[:3] == ["uv", "run", "--no-sync"]
    assert [command[index + 1] for index, token in enumerate(command) if token == "--only"] == ["alpha", "beta"]
    assert "--merge-into" in command
    assert command[command.index("--output") + 1] == ".artifacts/x.json"

    first = list(
        builder(
            ["alpha"],
            manifest=Path("m.json"),
            output=Path("o.json"),
            merge_into=False,
            repo_root=Path("."),
        )
    )
    assert "--merge-into" not in first, "첫 배치에 --merge-into 를 붙이면 이어받을 이전 보고서가 없다"


def test_the_real_manifest_keeps_the_three_gate_stages_meaningful(
    procedure: ModuleType, manifest_ids: list[str]
) -> None:
    """실제 manifest 로도 세 배치가 의미를 갖는지(무거운 셋이 실제로 required 인지)."""
    for gate_id in ("python-tests", "docker-build", "clean-machine-runtime"):
        assert gate_id in manifest_ids, f"{gate_id} 가 manifest 의 required 가 아니다"
    assert len(manifest_ids) >= 20


# ---------------------------------------------------------------------------
# 보고서 편입 — 마감의 마지막 한 걸음
# ---------------------------------------------------------------------------


def test_file_report_copies_the_report_into_the_evidence_tree(procedure: ModuleType, tmp_path: Path) -> None:
    source = tmp_path / "commercial-ga-close.json"
    payload = {"git": {"sha": "a" * 40, "tree_fingerprint": "b" * 64}, "gates": [], "summary": {}}
    source.write_text(json.dumps(payload), encoding="utf-8")
    attempt_dir = tmp_path / "evidence" / "attempt-999"

    target = procedure.file_report(source, attempt_dir)

    assert target == attempt_dir / "gate-report.json"
    assert json.loads(target.read_text(encoding="utf-8")) == payload


def test_teeth_file_report_refuses_missing_or_broken_source(procedure: ModuleType, tmp_path: Path) -> None:
    """없는 보고서·JSON 이 아닌 보고서는 증거로 편입되지 않는다(깨진 증거 금지)."""
    attempt_dir = tmp_path / "evidence" / "attempt-999"
    file_report = procedure.file_report
    assert isinstance(file_report, Callable)
    with pytest.raises(procedure.UsageError):
        file_report(tmp_path / "없다.json", attempt_dir)

    broken = tmp_path / "broken.json"
    broken.write_text("{ 깨진 보고서", encoding="utf-8")
    with pytest.raises(procedure.UsageError):
        file_report(broken, attempt_dir)
    assert not (attempt_dir / "gate-report.json").exists()


# ---------------------------------------------------------------------------
# close 단계 — 편입 + 마감 검사
# ---------------------------------------------------------------------------


def test_close_stage_files_the_report_then_passes(procedure: ModuleType, tmp_path: Path) -> None:
    """close 단계는 보고서를 편입하고 마감 검사까지 돌린다 — 순서가 뒤집히면 아무것도 증명하지 못한다."""
    repo = tmp_path / "repo"
    repo.mkdir()
    evidence = repo / ".omo" / "evidence" / "CR-14"
    manifest = repo / "gates.json"
    manifest.write_text(
        json.dumps({"gates": [{"id": "alpha", "required": True, "command": ["true"]}]}), encoding="utf-8"
    )
    sha = _init_repo(repo)
    fingerprint = _fingerprint(repo, "HEAD")
    card = repo / "card.md"
    card.write_text(
        f"- code candidate full SHA: **`{sha}`**\n"
        f"- 보조 식별자 코드 지문 **`{fingerprint}`**\n"
        "- required gate inventory / PASS / FAIL / NOT_RUN: **1 / 1 / 0 / 0**\n",
        encoding="utf-8",
    )
    report = {
        "git": {"sha": sha, "tree_fingerprint": fingerprint},
        "manifest": {"path": "gates.json", "sha256": _sha256(manifest)},
        "generated_at": "2026-09-13T00:00:00+00:00",
        "gates": [{"id": "alpha", "status": "passed", "exit_code": 0, "required": True, "duration_seconds": 1.0}],
        "summary": {"total": 1, "passed": 1, "failed": 0, "required_failed": 0},
    }
    artifacts = repo / ".artifacts"
    artifacts.mkdir()
    (artifacts / "commercial-ga-999-close.json").write_text(json.dumps(report), encoding="utf-8")

    code = procedure.main(
        [
            "--attempt",
            "attempt-999",
            "--stage",
            "close",
            "--manifest",
            str(manifest),
            "--card",
            str(card),
            "--evidence-root",
            str(evidence),
            "--repo-root",
            str(repo),
        ]
    )
    assert code == 0
    filed = json.loads((evidence / "attempt-999" / "gate-report.json").read_text(encoding="utf-8"))
    assert filed["git"]["tree_fingerprint"] == fingerprint


def test_teeth_close_stage_fails_when_the_report_is_missing(procedure: ModuleType, tmp_path: Path) -> None:
    """게이트를 돌리지 않은 채 close 를 부르면 **사용 오류(2)** 로 멈춘다 — 조용히 통과하지 않는다."""
    repo = tmp_path / "repo"
    repo.mkdir()
    manifest = repo / "gates.json"
    manifest.write_text(
        json.dumps({"gates": [{"id": "alpha", "required": True, "command": ["true"]}]}), encoding="utf-8"
    )
    code = procedure.main(
        [
            "--attempt",
            "attempt-998",
            "--stage",
            "close",
            "--manifest",
            str(manifest),
            "--card",
            str(repo / "card.md"),
            "--evidence-root",
            str(repo / ".omo"),
            "--repo-root",
            str(repo),
        ]
    )
    assert code == 2


def _init_repo(root: Path) -> str:
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=root, check=True, capture_output=True)
    (root / "app.py").write_text("value = 1\n", encoding="utf-8")
    options = ["-c", "user.name=cr14", "-c", "user.email=cr14@example.invalid", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", *options, "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", *options, "commit", "-q", "-m", "seed"], cwd=root, check=True, capture_output=True)
    return subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True, capture_output=True, text=True
    ).stdout.strip()


def _fingerprint(root: Path, rev: str) -> str:
    gate = _load(REPO_ROOT / "scripts" / "ga_gate.py", "cr14_ga_gate_close_procedure_under_test")
    return str(gate.tree_fingerprint_of_commit(root, rev, None))


def _sha256(path: Path) -> str:
    import hashlib

    return hashlib.sha256(path.read_bytes()).hexdigest()
