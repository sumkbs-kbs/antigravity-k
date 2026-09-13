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
        # 등록부도 **후보 커밋 안에** 둔다 — 나중에 만들면 그 파일이 첫 커밋에 섮여 "docs 전용" 검사가
        # 코드 스코프 이동으로 읽는다(계약이 재는 것이 그것이다).
        self.write_register([{"gate": "alpha", "observation": "none"}, {"gate": "beta", "observation": "none"}])
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
        # 기본 등록부 — manifest 의 게이트를 전수 덮되 관측 자리를 `none` 으로 둔다(스킵 관측은
        # 아래 테스트들이 개별적으로 켠다). 등록부가 **없으면** 마감 검사가 그것을 위반으로 본다.
        self.write_register([{"gate": gate_id, "observation": "none"} for gate_id in ids])

    def write_register(self, entries: list[dict[str, object]]) -> Path:
        path = self.repo / "scripts" / "gate_skip_register.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps({"schema_version": 1, "gate_visibility": {"gates": entries}}),
            encoding="utf-8",
        )
        return path

    def write_report(
        self,
        attempt: str,
        *,
        gates: list[tuple[str, str]] | None = None,
        raw_gates: list[dict[str, object]] | None = None,
        fingerprint: str | None = None,
        sha: str | None = None,
        generated_at: str = "2026-09-13T00:00:00+00:00",
        manifest_sha: str | None = None,
        outputs: dict[str, str] | None = None,
    ) -> Path:
        """보고서 하나를 쓴다 — `gates` 는 (id, status) 쌍, `raw_gates` 는 기록을 그대로 준다.

        `raw_gates` 가 필요한 이유: status 가 `passed`/`failed` 뿐이라고 가정하면 러너가 만들 수
        있는 **다른 상태**(`tree_moved` — F-34)를 이 하네스가 표현할 수 없고, 표현할 수 없는
        보고서는 검사할 수도 없다.
        """
        directory = self.evidence / attempt
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / "gate-report.json"
        records = raw_gates or [
            {
                "id": gate_id,
                "status": status,
                "exit_code": 0 if status == "passed" else 1,
                "required": True,
                "duration_seconds": 1.0,
                "stdout": (outputs or {}).get(gate_id, ""),
            }
            for gate_id, status in (gates or [])
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


# ---------------------------------------------------------------------------
# F-34 (attempt-026) — 게이트가 측정 대상 코드를 바꾸면 그 보고서는 단일 코드 상태가 아니다
# ---------------------------------------------------------------------------


def test_teeth_gate_that_moved_the_tree_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    """게이트가 추적 산출물을 다시 쓴 보고서 — required 실패가 하나도 없어도 마감할 수 없다.

    `tree_moved` 는 명령이 exit 0 인 상태라 `not_passed`/`bad_exit` 가 그것을 잡지 못하는 자리다.
    """
    fixture.write_report(
        "attempt-002",
        raw_gates=[
            {"id": "alpha", "status": "passed", "exit_code": 0, "required": True, "duration_seconds": 1.0},
            {
                "id": "beta",
                "status": "tree_moved",
                "exit_code": 0,
                "required": True,
                "duration_seconds": 1.0,
                "tree_moved": ["src/antigravity_k/dashboard_dist/assets/index-abc.js"],
            },
        ],
        generated_at="2026-09-13T01:00:00+00:00",
    )
    problems = fixture.check(closer, _card_text(fixture.candidate, fixture.fingerprint, (2, 1, 0, 1)))
    assert any("측정 대상 코드를 바꿨다" in problem for problem in problems), problems
    assert any("dashboard_dist/assets/index-abc.js" in problem for problem in problems), (
        f"어느 파일이 움직였는지 대지 않으면 다음 사람이 원인을 찾을 수 없다: {problems}"
    )


# ---------------------------------------------------------------------------
# R-16 (attempt-024) — 다른 게이트의 스킵도 소유되어야 한다
# ---------------------------------------------------------------------------


def test_close_check_gates_with_zero_skips_pass(closer: ModuleType, fixture: _Fixture) -> None:
    """기준선 — 관측 자리를 켜 두고도 스킵이 0건이면 마감할 수 있다(강한 검사도 초록을 낼 수 있어야 쓸 수 있다)."""
    fixture.write_register(
        [
            {"gate": "alpha", "attribution": "per_test", "observation": "close_check"},
            {"gate": "beta", "attribution": "no_skip_concept", "observation": "none"},
        ]
    )
    fixture.write_report(
        "attempt-002",
        gates=[("alpha", "passed"), ("beta", "passed")],
        outputs={"alpha": "9 passed, 16 deselected, 1 warning in 20.20s\n"},
        generated_at="2026-09-13T01:00:00+00:00",
    )
    assert fixture.check(closer, fixture.healthy_card()) == []


def test_teeth_skip_reported_by_a_close_check_gate_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    """게이트가 스킵을 보고했는데 등록부가 그 게이트를 `close_check` 로만 적어 두면 거부한다.

    이것이 R-16 의 이빨이다: 게이트 안에서 재현할 수 없는 게이트(docker·dashboard·playwright)의
    스킵은 **여기서만** 보인다. 이 조항이 없으면 한 게이트가 테스트를 통째로 빼고도 21/21 이 된다.
    """
    fixture.write_register(
        [
            {"gate": "alpha", "attribution": "per_test", "observation": "close_check"},
            {"gate": "beta", "attribution": "no_skip_concept", "observation": "none"},
        ]
    )
    fixture.write_report(
        "attempt-002",
        gates=[("alpha", "passed"), ("beta", "passed")],
        outputs={"alpha": "7 passed, 2 skipped, 16 deselected in 20.20s\n"},
        generated_at="2026-09-13T01:00:00+00:00",
    )
    problems = fixture.check(closer, fixture.healthy_card())
    assert any("스킵 2건을 보고했다" in problem and "alpha" in problem for problem in problems), problems


def test_teeth_shell_skip_row_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    """셸 스크립트 게이트의 `SKIP` 행도 같은 자리에서 잡는다(`clean-machine-runtime` 의 모양).

    그 행은 색상 이스케이프로 감싸여 나오므로 이스케이프를 벗긴 뒤 본다 — 실측으로 확인했다.
    """
    fixture.write_register(
        [
            {"gate": "alpha", "attribution": "no_skip_concept", "observation": "close_check"},
            {"gate": "beta", "attribution": "no_skip_concept", "observation": "none"},
        ]
    )
    fixture.write_report(
        "attempt-002",
        gates=[("alpha", "passed"), ("beta", "passed")],
        outputs={
            "alpha": "\x1b[33mwheel \uac80\uc99d   SKIP   -\x1b[0m\n\u2714 \ud074\ub9b0\uba38\uc2f6 \uc7ac\ud604 \uc131\uacf5\n"
        },
        generated_at="2026-09-13T01:00:00+00:00",
    )
    problems = fixture.check(closer, fixture.healthy_card())
    assert any("스킵 1건을 보고했다" in problem for problem in problems), problems


def test_teeth_gate_missing_from_the_visibility_register_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    """보고서에 있는 required 게이트가 등록부의 가시성 분류에 없으면 거부한다(소유자 없는 게이트)."""
    fixture.write_register([{"gate": "alpha", "attribution": "per_test", "observation": "close_check"}])
    problems = fixture.check(closer, fixture.healthy_card())
    assert any("가시성 분류에 없다" in problem and "beta" in problem for problem in problems), problems


def test_teeth_missing_register_is_rejected(closer: ModuleType, fixture: _Fixture) -> None:
    """등록부가 없으면 **침묵 통과하지 않는다** — 그 자리가 바로 소유자 없는 스킵이 숨는 자리다."""
    (fixture.repo / "scripts" / "gate_skip_register.json").unlink()
    problems = fixture.check(closer, fixture.healthy_card())
    assert any("가시성 등록부" in problem for problem in problems), problems


def test_registered_gate_keeps_its_skips_at_close(closer: ModuleType, fixture: _Fixture) -> None:
    """`registered` 게이트(`python-tests`)의 스킵은 등록부가 소유한다 — 마감 검사가 그것을 거부하지 않는다.

    어떻게 박아 두는가: 이 조항을 `close_check` 게이트에만 걸어 두었다. 그렇지 않으면
    python-tests 의 13건이 마감마다 위반으로 올라와 검사가 쓸 수 없게 된다.
    """
    fixture.write_register(
        [
            {"gate": "alpha", "attribution": "per_test", "observation": "registered"},
            {"gate": "beta", "attribution": "no_skip_concept", "observation": "none"},
        ]
    )
    fixture.write_report(
        "attempt-002",
        gates=[("alpha", "passed"), ("beta", "passed")],
        outputs={"alpha": "6291 passed, 13 skipped, 16 deselected in 559.48s\n"},
        generated_at="2026-09-13T01:00:00+00:00",
    )
    assert fixture.check(closer, fixture.healthy_card()) == []


def test_the_real_manifest_is_the_one_this_check_reads() -> None:
    """이 검사가 실제로 읽는 manifest 와 게이트 인벤토리 계약이 같은 파일인지 확인한다."""
    payload = json.loads(_MANIFEST.read_text(encoding="utf-8"))
    ids = sorted(str(gate["id"]) for gate in payload["gates"] if gate.get("required"))
    assert len(ids) == len(payload["gates"]), "모든 gate 가 required 라는 전제가 깨졌다"
    assert "python-tests" in ids and len(ids) >= 20
