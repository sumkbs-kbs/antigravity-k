"""CR-14 — **마감 절차**(`scripts/run_attempt_close.py`)와 그 이빨 (R-10).

attempt-016 은 마감 검사를 만들고 "사람이(또는 절차가) 돌려야 작동한다"를 한계 R-10 으로 남겼다.
이 파일은 그 절차가 **게이트 목록을 manifest 에서 읽고**, 배치 경계마다 `--merge-into` 를 붙이고,
보고서를 증거 트리에 **편입한 뒤에만** 마감 검사를 통과시키는지를 고정한다.

왜 이빨이 필요한가: 절차가 게이트 목록을 **스스로 들고 있으면**(개수·이름을 하드코딩하면) manifest 에
게이트를 추가해도 그 게이트는 돌지 않는다 — 검사를 빼는 경로가 조용히 열린다(F-21 이 개수 고정을
목록 고정으로 바꾼 이유, C14-01c 이 인벤토리를 못 박은 이유와 같은 병). 그래서 배치 계획을
**순수 함수**(`plan_stage(stage, gate_ids)`)로 두고, 임의의 목록을 넣어 확인한다.

attempt-017 은 그 이어받기 **판단**을 `(후보 sha, manifest sha256)` 으로 정의했는데, 그것은
게이트 규칙(`ga_gate.merge_refusal_reason`: + **작업 트리 지문**)의 **부분 복제**였다 — 두 주체가
갈라지는 조합이 실재했고, 그래서 attempt-018 이 판단을 게이트에 **위임**하고 거부를 **조용한
새 시작**이 아니라 이유를 대는 중단(exit 2)으로 바꿨다(F-27). 그 이빨이 아래에 있다.

이 파일은 실제 게이트를 돌리지 않는다(10분이 걸린다) — 그 부분은 attempt-018 실측이 증거다.
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


def test_merge_is_decided_by_the_report_identity_not_by_stage_order(procedure: ModuleType, tmp_path: Path) -> None:
    """F-26 — 이어받기는 **파일의 정체성**으로 결정한다(그리고 F-27 — 세 축을 다 본다).

    배치를 따로 실행하면(각 호출이 별도 프로세스) "첫 배치인가"를 프로세스 안에서 알 수 없다.
    첫 구현은 그 상태로 "첫 배치에만 --merge-into 를 안 붙이는" 규칙을 써서, `--stage tests`
    단독 실행이 fast 18개의 결과를 **덮어썼다**(보고서 total 18 → 1).
    """
    output = tmp_path / "report.json"
    sha, manifest_sha, fingerprint = "a" * 40, "c" * 64, "e" * 64
    decide = procedure.merge_decision
    assert isinstance(decide, Callable)
    assert decide(output, sha=sha, manifest_sha=manifest_sha, tree_fingerprint=fingerprint) == "fresh"

    def write_report(*, report_sha: str, report_manifest: str, report_fingerprint: str) -> None:
        output.write_text(
            json.dumps(
                {
                    "git": {"sha": report_sha, "tree_fingerprint": report_fingerprint},
                    "manifest": {"sha256": report_manifest},
                }
            ),
            encoding="utf-8",
        )

    write_report(report_sha=sha, report_manifest=manifest_sha, report_fingerprint=fingerprint)
    assert decide(output, sha=sha, manifest_sha=manifest_sha, tree_fingerprint=fingerprint) == "merge"

    write_report(report_sha="b" * 40, report_manifest=manifest_sha, report_fingerprint=fingerprint)
    assert decide(output, sha=sha, manifest_sha=manifest_sha, tree_fingerprint=fingerprint) != "merge"  # 다른 후보

    write_report(report_sha=sha, report_manifest="d" * 64, report_fingerprint=fingerprint)
    assert decide(output, sha=sha, manifest_sha=manifest_sha, tree_fingerprint=fingerprint) != "merge"  # 다른 manifest

    # F-27 — **세 번째 축**이다. attempt-017 의 판단은 이 축을 보지 않아 게이트와 갈라졌다.
    write_report(report_sha=sha, report_manifest=manifest_sha, report_fingerprint="f" * 64)
    assert decide(output, sha=sha, manifest_sha=manifest_sha, tree_fingerprint=fingerprint) != "merge"

    output.write_text("{ 깨진 보고서", encoding="utf-8")
    assert decide(output, sha=sha, manifest_sha=manifest_sha, tree_fingerprint=fingerprint) != "merge"


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


def test_teeth_second_stage_does_not_erase_the_first_stage_results(procedure: ModuleType, tmp_path: Path) -> None:
    """F-26 의 모양 그대로 — 앞 배치의 결과가 들어 있는 보고서를 두 번째 배치가 **덮어쓰지 않는다**.

    실제 실행 없이 규칙만 확인한다: 같은 후보·manifest 의 보고서가 있으면 `--merge-into` 가 붙고,
    그 플래그가 붙은 argv 로 같은 출력 파일을 쓰므로 ga_gate 가 이어받는다(그 이어받기 규칙은
    `tests/test_cr14_candidate_evidence.py` 가 따로 고정한다).
    """
    output = tmp_path / "report.json"
    sha, manifest_sha, fingerprint = "e" * 40, "f" * 64, "a" * 64
    output.write_text(
        json.dumps({"git": {"sha": sha, "tree_fingerprint": fingerprint}, "manifest": {"sha256": manifest_sha}}),
        encoding="utf-8",
    )
    decides = (
        procedure.merge_decision(output, sha=sha, manifest_sha=manifest_sha, tree_fingerprint=fingerprint) == "merge"
    )
    assert decides is True
    command = list(
        procedure.gate_command(
            ["python-tests"],
            manifest=tmp_path / "gates.json",
            output=output,
            merge_into=decides,
            repo_root=tmp_path,
        )
    )
    assert "--merge-into" in command
    assert str(tmp_path / "scripts" / "ga_gate.py") in command


def test_close_stage_files_the_report_then_passes(procedure: ModuleType, tmp_path: Path) -> None:
    """close 단계는 보고서를 편입하고 마감 검사까지 돌린다 — 순서가 뒤집히면 아무것도 증명하지 못한다."""
    repo = tmp_path / "repo"
    repo.mkdir()
    evidence = repo / ".omo" / "evidence" / "CR-14"
    manifest = repo / "gates.json"
    manifest.write_text(
        json.dumps({"gates": [{"id": "alpha", "required": True, "command": ["true"]}]}), encoding="utf-8"
    )
    # 게이트별 스킵 가시성 등록부 — attempt-024(R-16)부터 마감 검사가 이를 요구한다:
    # 등록부가 없으면 "소유자 없는 스킵"을 판정할 수 없으므로 FAIL 이다(침묵을 통과로 읽지 않는다).
    scripts = repo / "scripts"
    scripts.mkdir()
    (scripts / "gate_skip_register.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "gate_visibility": {
                    "gates": [{"gate": "alpha", "attribution": "no_skip_concept", "observation": "none"}]
                },
            }
        ),
        encoding="utf-8",
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


# ---------------------------------------------------------------------------
# F-27 이빨 — 판단이 게이트 규칙의 **복제**가 아니라 **위임**인가
# ---------------------------------------------------------------------------


def test_merge_decision_delegates_to_the_gate_rule(
    procedure: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """판단이 **게이트의 함수를 묻는지** — 절차 안에 사본이 있으면 이 이빨이 깨진다.

    게이트의 함수를 바꿔도 답이 그대로라면 그것은 복제다. 답이 따라 움직여야 한다.
    """
    output = tmp_path / "report.json"
    output.write_text(
        json.dumps({"git": {"sha": "a" * 40, "tree_fingerprint": "e" * 64}, "manifest": {"sha256": "c" * 64}}),
        encoding="utf-8",
    )
    gate = procedure._GATE

    def state() -> str:
        return str(procedure.merge_decision(output, sha="a" * 40, manifest_sha="c" * 64, tree_fingerprint="e" * 64))

    assert state() == "merge", "기준선 — 보고서는 이어받을 수 있는 상태다"
    monkeypatch.setattr(gate, "merge_refusal_reason", lambda *args, **kwargs: "게이트가 거부했다")
    assert state() == "게이트가 거부했다", "절차가 자기 규칙을 들고 있으면 게이트의 답을 따르지 않는다"


@pytest.mark.parametrize(
    ("report_sha", "report_manifest", "report_fingerprint", "merges"),
    [
        ("a" * 40, "c" * 64, "e" * 64, True),
        ("b" * 40, "c" * 64, "e" * 64, False),
        ("a" * 40, "d" * 64, "e" * 64, False),
        ("a" * 40, "c" * 64, "f" * 64, False),
    ],
)
def test_the_procedure_never_merges_what_the_gate_would_refuse(
    procedure: ModuleType,
    tmp_path: Path,
    report_sha: str,
    report_manifest: str,
    report_fingerprint: str,
    merges: bool,
) -> None:
    """세 축 각각에서 "절차가 이어받는다" == "게이트도 이어받는다" — 두 주체가 갈라지지 않는다."""
    output = tmp_path / "report.json"
    output.write_text(
        json.dumps(
            {
                "git": {"sha": report_sha, "tree_fingerprint": report_fingerprint},
                "manifest": {"sha256": report_manifest},
            }
        ),
        encoding="utf-8",
    )
    gate_accepts = procedure._GATE.merge_refusal_reason(output, "a" * 40, "c" * 64, "e" * 64) is None
    decided = (
        procedure.merge_decision(output, sha="a" * 40, manifest_sha="c" * 64, tree_fingerprint="e" * 64) == "merge"
    )
    assert decided == gate_accepts, "절차와 게이트가 다른 답을 냈다(F-27 이 재현되던 자리)"
    assert decided is merges


def test_teeth_a_refused_merge_aborts_and_keeps_the_report(
    procedure: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """F-27 — 이어받을 수 없는 보고서를 **조용히 버리지 않는다**.

    attempt-017 의 절차는 이 자리에서 `[merge] 새 보고서로 시작한다` 를 찍고 exit 0 으로 넘어갔다 —
    게이트 단계를 하나라도 돌리면 앞 배치의 초록이 사라졌다. 이제는 이유를 대며 exit 2 로 끓고,
    보고서를 **덮어쓰지 않는다**.
    """
    root = tmp_path / "repo"
    root.mkdir()
    _init_repo(root)
    output = root / ".artifacts" / "commercial-ga-777-close.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "git": {"sha": "0" * 40, "tree_fingerprint": "1" * 64},
                "manifest": {"sha256": "2" * 64},
                "gates": [{"id": "python-ruff", "status": "passed", "exit_code": 0, "required": True}],
            }
        ),
        encoding="utf-8",
    )
    before = _sha256(output)
    code = procedure.main(
        [
            "--attempt",
            "attempt-777",
            "--stage",
            "fast",
            "--manifest",
            str(_MANIFEST),
            "--evidence-root",
            str(root / ".omo"),
            "--repo-root",
            str(root),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2, "다른 코드 상태의 초록 위에 이어 쓰면 안 된다"
    assert "이어받을 수 없다" in captured.err
    assert "rm " in captured.err, "새로 시작하려는 사람에게 **명시적** 한 걸음을 알려준다"
    assert _sha256(output) == before, "거부된 보고서를 덮어쓰면 앞 배치의 초록이 조용히 사라진다"


def test_teeth_close_only_does_not_consult_the_merge_decision(
    procedure: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """기록 커밋 뒤의 `--stage close` 재확인을 이어받기 판단이 막지 않는다.

    `close` 는 게이트를 돌리지 않으므로 이어받을 것이 없다 — 사후 기록 커밋(docs 전용)이 후보
    SHA 를 옮겨도 이 단계는 계속 돌아야 한다(그것이 지문 불변 확인의 자리다).
    """
    root = tmp_path / "repo"
    root.mkdir()
    _init_repo(root)
    output = root / ".artifacts" / "commercial-ga-778-close.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {"git": {"sha": "0" * 40, "tree_fingerprint": "1" * 64}, "manifest": {"sha256": "2" * 64}, "gates": []}
        ),
        encoding="utf-8",
    )
    procedure.main(
        [
            "--attempt",
            "attempt-778",
            "--stage",
            "close",
            "--manifest",
            str(_MANIFEST),
            "--card",
            str(REPO_ROOT / "docs" / "ga" / "CR14_FINAL_CANDIDATE_VERDICT.md"),
            "--evidence-root",
            str(root / ".omo"),
            "--repo-root",
            str(root),
        ]
    )
    captured = capsys.readouterr()
    assert "이어받을 수 없다" not in captured.err, "close 는 게이트를 돌리지 않는다 — 판단할 것이 없다"
    assert "이어받기 판단이 필요 없다" in captured.out


def test_teeth_an_unreadable_card_is_a_usage_error(
    procedure: ModuleType, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """사용 오류는 exit 2 다 — 카드를 읽을 수 없을 때만 그 관례가 깨져 있었다(추적)"""
    root = tmp_path / "repo"
    root.mkdir()
    _init_repo(root)
    output = root / ".artifacts" / "commercial-ga-779-close.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"gates": []}), encoding="utf-8")
    code = procedure.main(
        [
            "--attempt",
            "attempt-779",
            "--stage",
            "close",
            "--manifest",
            str(_MANIFEST),
            "--card",
            str(root / "missing-card.md"),
            "--evidence-root",
            str(root / ".omo"),
            "--repo-root",
            str(root),
        ]
    )
    captured = capsys.readouterr()
    assert code == 2
    assert "ERROR" in captured.err


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
