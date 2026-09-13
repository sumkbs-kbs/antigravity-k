"""CR-14 — **attempt 마감 검사**(`scripts/verify_attempt_close.py`)와 그 이빨.

닫으려는 구멍 (R-9, attempt-015 한계)
=====================================
`tests/test_cr14_fence_movement_detection.py`(C14-F23)는 "보고서가 **있으면** 그 보고서가 자기가
이름 붙인 트리를 측정했는가"를 본다. 그 계약은 **보고서의 존재**를 요구할 수 없다 — 보고서는
게이트 실행이 끝날 때 쓰이므로 그 실행 **안에서는** 존재할 수 없다(순환). 그래서 required gate
21개를 전부 통과한 뒤에도 **"카드가 선언한 지문을 측정한 보고서가 실제로 있는가"** 를 묻는 자리가
비어 있었다. attempt-013 의 21/21 이 HEAD 가 아닌 트리를 가리키게 됐을 때 아무도 묻지 않은 것도
같은 구멍이다.

마감 검사는 게이트 **밖에서** 한 번 돌아 카드의 주장과 증거 파일을 대조한다:
  ① 선언 자리가 각각 하나 ② 선언된 지문을 측정한 보고서가 있는가 ③ 그 보고서가 이름 붙인 커밋의
코드 트리 == 보고서 지문 ④ manifest sha256·required 목록 일치 ⑤ required 전부 passed·
exit 0·같은 지문에 실패한 실행 없음 ⑥ 카드 수치 == 보고서 집계 ⑦ 후보..HEAD 코드 스코프 변경 0건.

왜 이 파일이 필요한가: 마감 검사가 **게이트가 아니므로** 게이트가 자기 자신을 검사하지 못한다.
그래서 판정 로직을 임시 저장소·임시 증거 트리로 직접 두드려 이빨을 확인한다(이 파일은 실제
증거를 읽지 않는다 — 실제 카드·보고서는 `tests/test_cr14_fence_movement_detection.py` 의 조항 ④와
검토자의 수동 QA 가 본다).
"""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
_CLOSER_SCRIPT = REPO_ROOT / "scripts" / "verify_attempt_close.py"
_MANIFEST = REPO_ROOT / "scripts" / "commercial_ga_gates.json"

_SHA = "a" * 40
_FINGERPRINT = "b" * 64


def _load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def closer() -> ModuleType:
    return _load(_CLOSER_SCRIPT, "cr14_attempt_close_under_test")


def _git(root: Path, *args: str) -> str:
    result = subprocess.run(["git", *args], cwd=root, check=True, capture_output=True, text=True)
    return result.stdout.strip()


def _commit_all(root: Path, message: str) -> str:
    options = ["-c", "user.name=cr14", "-c", "user.email=cr14@example.invalid", "-c", "commit.gpgsign=false"]
    subprocess.run(["git", *options, "add", "-A"], cwd=root, check=True, capture_output=True)
    subprocess.run(["git", *options, "commit", "-q", "-m", message], cwd=root, check=True, capture_output=True)
    return _git(root, "rev-parse", "HEAD")


def _fingerprint(root: Path, rev: str) -> str:
    gate = _load(REPO_ROOT / "scripts" / "ga_gate.py", "cr14_ga_gate_attempt_close_under_test")
    compute = gate.tree_fingerprint_of_commit
    assert isinstance(compute, Callable)
    return str(compute(root, rev, None))


def _card_text(candidate: str, fingerprint: str, numbers: tuple[int, int, int, int]) -> str:
    inventory, passed, failed, not_run = numbers
    return (
        "# 후보 판정서\n\n"
        f"- code candidate full SHA: **`{candidate}`**\n"
        f"- 지문: 보조 식별자 코드 지문 **`{fingerprint}`**(테스트용)\n"
        f"- required gate inventory / PASS / FAIL / NOT_RUN: **{inventory} / {passed} / {failed} / {not_run}**\n"
    )


class _Fixture:
    """임시 저장소 + 임시 증거 트리 + 임시 manifest 한 벌."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.evidence = root / ".omo" / "evidence" / "CR-14"
        self.evidence.mkdir(parents=True)
        self.repo = root / "repo"
        self.repo.mkdir()
        (self.repo / "src").mkdir()
        (self.repo / "docs").mkdir()
        (self.repo / "src" / "app.py").write_text("value = 1\n", encoding="utf-8")
        (self.repo / "docs" / "plan.md").write_text("plan\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q"], cwd=self.repo, check=True, capture_output=True)
        self.candidate = _commit_all(self.repo, "seed")
        self.fingerprint = _fingerprint(self.repo, "HEAD")
        self.manifest = root / "gates.json"
        self.write_manifest(["alpha", "beta"])
        self.write_report("attempt-001", gates=[("alpha", "passed"), ("beta", "passed")])

    def write_manifest(self, ids: list[str]) -> None:
        self.manifest.write_text(
            json.dumps(
                {
                    "gates": [
                        {"id": gate_id, "required": True, "command": ["true"], "category": "python_backend"}
                        for gate_id in ids
                    ]
                }
            ),
            encoding="utf-8",
        )
        self.manifest_sha = __import__("hashlib").sha256(self.manifest.read_bytes()).hexdigest()

    def write_report(
        self,
        attempt: str,
        *,
        gates: list[tuple[str, str]],
        fingerprint: str | None = None,
        sha: str | None = None,
        generated_at: str = "2026-09-13T00:00:00+00:00",
        manifest_sha: str | None = None,
    ) -> Path:
        directory = self.evidence / attempt
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "gate-report.json"
        records = [
            {
                "id": gate_id,
                "status": status,
                "exit_code": 0 if status == "passed" else 1,
                "required": True,
                "duration_seconds": 1.0,
            }
            for gate_id, status in gates
        ]
        passed = sum(1 for record in records if record["status"] == "passed")
        path.write_text(
            json.dumps(
                {
                    "git": {"sha": sha or self.candidate, "tree_fingerprint": fingerprint or self.fingerprint},
                    "manifest": {"path": "gates.json", "sha256": manifest_sha or self.manifest_sha},
                    "generated_at": generated_at,
                    "gates": records,
                    "summary": {
                        "total": len(records),
                        "passed": passed,
                        "failed": len(records) - passed,
                        "required_failed": sum(1 for record in records if record["status"] != "passed"),
                    },
                }
            ),
            encoding="utf-8",
        )
        return path

    def check(self, closer: ModuleType, card: str) -> list[str]:
        return list(
            closer.close_violations(
                card_text=card,
                repo_root=self.repo,
                evidence_root=self.evidence,
                manifest_path=self.manifest,
            )
        )

    def healthy_card(self) -> str:
        return _card_text(self.candidate, self.fingerprint, (2, 2, 0, 0))


@pytest.fixture()
def fixture(tmp_path: Path) -> _Fixture:
    return _Fixture(tmp_path)


# ---------------------------------------------------------------------------
# 계약 — 정합한 상태는 통과해야 한다(그러지 않으면 검사가 쓸 수 없다)
# ---------------------------------------------------------------------------


def test_consistent_evidence_passes(closer: ModuleType, fixture: _Fixture) -> None:
    assert fixture.check(closer, fixture.healthy_card()) == []


def test_teeth_missing_report_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    """R-9 의 핵심 — 선언한 지문을 측정한 보고서가 없으면 마감할 수 없다."""
    for path in fixture.evidence.glob("attempt-*/gate-report.json"):
        path.unlink()
    problems = fixture.check(closer, fixture.healthy_card())
    assert problems and "선언된 지문을 측정한 gate 보고서가 없다" in problems[0]


def test_teeth_report_for_another_fingerprint_does_not_count(closer: ModuleType, fixture: _Fixture) -> None:
    """다른 트리를 측정한 보고서가 아무리 많아도 선언한 지문의 증거가 될 수 없다."""
    for path in fixture.evidence.glob("attempt-*/gate-report.json"):
        path.unlink()
    fixture.write_report("attempt-002", gates=[("alpha", "passed"), ("beta", "passed")], fingerprint="c" * 64)
    problems = fixture.check(closer, fixture.healthy_card())
    assert problems and "선언된 지문을 측정한 gate 보고서가 없다" in problems[0]


def test_teeth_report_measured_on_a_dirty_tree_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    """보고서가 이름 붙인 커밋의 트리 != 보고서 지문 — 커밋되지 않은 트리를 잰 보고서."""
    (fixture.repo / "src" / "app.py").write_text("value = 2\n", encoding="utf-8")
    dirty = _load(REPO_ROOT / "scripts" / "ga_gate.py", "cr14_ga_gate_worktree_probe")._tree_fingerprint(fixture.repo)
    fixture.write_report("attempt-002", gates=[("alpha", "passed"), ("beta", "passed")], fingerprint=dirty)
    problems = fixture.check(closer, _card_text(fixture.candidate, dirty, (2, 2, 0, 0)))
    assert any("코드 트리와 다르다" in problem for problem in problems), problems


def test_teeth_failed_required_gate_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    fixture.write_report("attempt-002", gates=[("alpha", "passed"), ("beta", "failed")])
    problems = fixture.check(closer, _card_text(fixture.candidate, fixture.fingerprint, (2, 1, 1, 0)))
    assert any("required gate 실패가 있다" in problem for problem in problems), problems


def test_teeth_manifest_drift_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    """게이트 목록이 바뀐 뒤 재측정하지 않으면(manifest sha256 불일치) 마감할 수 없다."""
    fixture.write_manifest(["alpha", "beta", "gamma"])
    problems = fixture.check(closer, fixture.healthy_card())
    assert any("manifest sha256" in problem for problem in problems), problems


def test_teeth_inventory_drift_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    """개수만 맞추고 **목록**이 다른 경로(검사를 빼고 다른 검사를 넣기)를 막는다."""
    fixture.write_manifest(["alpha", "gamma"])
    fixture.write_report("attempt-002", gates=[("alpha", "passed"), ("gamma", "passed")])
    problems = fixture.check(closer, fixture.healthy_card())
    assert any("required gate 목록이 manifest 와 다르다" in problem for problem in problems), problems


def test_teeth_card_numbers_must_come_from_the_report(closer: ModuleType, fixture: _Fixture) -> None:
    """손으로 적은 수치 금지 — 카드의 21/21/0/0 은 보고서 집계와 같아야 한다."""
    problems = fixture.check(
        closer,
        _card_text(fixture.candidate, fixture.fingerprint, (2, 2, 0, 0)).replace(
            "**2 / 2 / 0 / 0**", "**21 / 21 / 0 / 0**"
        ),
    )
    assert any("선언한 게이트 수치" in problem for problem in problems), problems


def test_teeth_summary_inconsistency_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    """summary 만 손으로 고친 보고서(게이트는 실패인데 summary 는 초록)를 거부한다."""
    path = fixture.evidence / "attempt-001" / "gate-report.json"
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["gates"][1]["status"] = "failed"
    path.write_text(json.dumps(payload), encoding="utf-8")
    problems = fixture.check(closer, fixture.healthy_card())
    assert any("보고서 summary" in problem for problem in problems), problems


def test_teeth_fence_move_after_the_candidate_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    """기록 커밋이 코드 스코프를 건드리면(README·tests·설정) 마감할 수 없다 — F-22 의 모양."""
    (fixture.repo / "README.md").write_text("current state\n", encoding="utf-8")
    _commit_all(fixture.repo, "docs: record that touches the code scope")
    problems = fixture.check(closer, fixture.healthy_card())
    assert any("후보 뒤에 코드 스코프가 움직였다" in problem and "README.md" in problem for problem in problems)


def test_teeth_docs_only_commit_after_the_candidate_is_accepted(closer: ModuleType, fixture: _Fixture) -> None:
    (fixture.repo / "docs" / "plan.md").write_text("plan v2\n", encoding="utf-8")
    _commit_all(fixture.repo, "docs: record")
    assert fixture.check(closer, fixture.healthy_card()) == []


def test_teeth_duplicate_declaration_sites_are_a_usage_error(closer: ModuleType, fixture: _Fixture) -> None:
    card = fixture.healthy_card() + f"\n- 다른 해석의 코드 지문 **`{'c' * 64}`**\n"
    with pytest.raises(closer.UsageError):
        fixture.check(closer, card)


def test_usage_error_for_an_unknown_candidate(closer: ModuleType, fixture: _Fixture) -> None:
    with pytest.raises(closer.UsageError):
        fixture.check(closer, _card_text("d" * 40, fixture.fingerprint, (2, 2, 0, 0)))


def test_exit_codes_match_the_verdict(closer: ModuleType, fixture: _Fixture) -> None:
    """CLI 계약 — 0 = 마감 가능, 1 = FAIL, 2 = 사용 오류(`ga_gate_verify.py` 와 같은 관례)."""
    card = fixture.root / "card.md"
    card.write_text(fixture.healthy_card(), encoding="utf-8")
    base = [
        "--card",
        str(card),
        "--evidence-root",
        str(fixture.evidence),
        "--manifest",
        str(fixture.manifest),
        "--repo-root",
        str(fixture.repo),
    ]
    assert closer.main(base) == 0
    card.write_text(_card_text(fixture.candidate, fixture.fingerprint, (9, 9, 0, 0)), encoding="utf-8")
    assert closer.main(base) == 1
    (fixture.evidence / "attempt-001" / "gate-report.json").write_text("{not json", encoding="utf-8")
    assert closer.main([*base, "--card", str(fixture.root / "missing-card.md")]) == 2


def test_the_real_manifest_is_the_one_this_check_reads() -> None:
    """이 검사가 실제로 읽는 manifest 와 게이트 인벤토리 계약이 같은 파일인지 확인한다."""
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    ids = sorted(str(gate["id"]) for gate in payload["gates"] if gate.get("required"))
    assert len(ids) == len(payload["gates"]), "모든 gate 가 required 라는 전제가 깨졌다"
    assert "python-tests" in ids and len(ids) >= 20
