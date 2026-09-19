"""계약 시험(승격본) — cue lexicon 의 **작동하는 부분**은 고정하고, **알려진 결함**은 드러낸다.

왜 이렇게 쓰는가: 측정([nx01/cue-lexicon-measurement.md](../../nx01/cue-lexicon-measurement.md))이
"사전 밖 표현 12/12 누락 · 잉여 승격 6/7 · 실제 경로 피해 3건"을 기록했다. 결함을 `assert defect == True`
로 적으면 **고쳐도 초록**이고, 아예 안 적으면 **다음 사람이 모른다**. 그래서:

* 지금 성립하는 계약(사전 표현은 잡힌다 · 명시적 해제는 무효화된다 · 무관한 편집은 무효화하지 않는다)은 assert 한다.
* 지금 성립하지 않는 것(바꿔쓰기 누락 · 잉여 승격 · 편집 지시에 의한 상시 규칙 무효화)은 **strict xfail** 로 적는다.
  어휘를 고치면 그 시험들이 **예상 밖 통과**로 실패하고, 그때 측정 문서와 이 파일을 함께 갱신하게 된다.

승격 상태: `tests/test_cue_lexicon_contract.py` 로 옮겨진다. 케이스 표는 측정기가 소유하고
(`scripts/cue_lexicon_probe.py`), 이 파일은 계약만 소유한다(중복 데이터를 만들지 않는다).
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any

import pytest

from antigravity_k.engine.summary_memory import (
    STATUS_SUPERSEDED,
    SummaryMemory,
    update_from_messages,
)


def _repo_root() -> Path:
    for parent in Path(__file__).resolve().parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    raise AssertionError("저장소 루트를 찾지 못했다(pyproject.toml 없음)")


REPO = _repo_root()
_PROBE_CANDIDATES = (
    REPO / "scripts" / "cue_lexicon_probe.py",
    REPO / "docs" / "qa" / "2026-09-16-followup" / "nx01" / "cue_lexicon_probe.py",
)


def _load_probe() -> Any:
    path = next((c for c in _PROBE_CANDIDATES if c.is_file()), None)
    if path is None:
        pytest.fail(f"측정기를 찾지 못했다: {[str(c.relative_to(REPO)) for c in _PROBE_CANDIDATES]}")
    spec = importlib.util.spec_from_file_location("cue_lexicon_probe_under_test", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module  # dataclass 가 sys.modules 를 찾는다 — 먼저 등록한다
    spec.loader.exec_module(module)
    return module


PROBE = _load_probe()
CASES = list(PROBE.CASES)
DIRECT_HITS = {
    case.text: case.expected
    for case in CASES
    if case.family == "A_direct" and case.text != "배포 전에 반드시 나에게 물어봐"
}
# 계약은 케이스를 **명시적으로** 나눈다 — 자동 분류(‘지금 None 이면 통과로 친다’)는
# 새로 생긴 결함을 조용히 삼키므로 쓰지 않는다.
NO_CUE_CONTROLS = ("이 로그 좀 봐주세요",)  # 사전 단어가 하나도 없는 문장 — 규칙이 아니어야 한다
PARAPHRASES = [case for case in CASES if case.family == "B_paraphrase"]
FALSE_POSITIVES = [case for case in CASES if case.family == "C_false_positive" and case.text not in NO_CUE_CONTROLS]


def _kind(text: str) -> str | None:
    return PROBE.detect_kind(text)


def _constraint_status(speech: tuple[str, ...], tracked: str) -> str:
    """실제 경로(`update_from_messages`)로 발화를 넣고 추적 문장의 상태를 본다(‘absent’ 포함)."""
    memory = SummaryMemory()
    messages = [{"id": f"m{i}", "role": "user", "content": content} for i, content in enumerate(speech)]
    update_from_messages(memory, messages, revision=1)
    found = next((c for c in memory.constraints if c.text == tracked), None)
    return "absent" if found is None else found.status


# ── 지금 성립하는 계약 ──────────────────────────────────────────────────


@pytest.mark.parametrize(("text", "expected"), sorted(DIRECT_HITS.items()))
def test_lexicon_cues_are_structured_with_the_right_kind(text: str, expected: str) -> None:
    """사전 표현으로 명시된 규칙은 구조화된다(이게 깨지면 기억 보존의 근간이 무너진다)."""
    assert _kind(text) == expected, f"{text!r} → {_kind(text)!r}"


def test_explicit_release_supersedes_without_deleting() -> None:
    """명시적 해제는 이전 항목을 **삭제하지 않고** status 만 바꾼다(‘조용한 삭제 금지’ 계약)."""
    assert (
        _constraint_status(
            ("네트워크 사용은 금지합니다", "이제부터 네트워크 써도 돼, 더 이상 금지 아님"), "네트워크 사용은 금지합니다"
        )
        == STATUS_SUPERSEDED
    )


@pytest.mark.parametrize("text", NO_CUE_CONTROLS)
def test_message_without_any_cue_is_not_a_constraint(text: str) -> None:
    """cue 가 하나도 없는 문장은 규칙이 아니다 — 이게 깨지면 모든 발화가 규칙이 된다(양성 대조군)."""
    assert _kind(text) is None


def test_unrelated_edit_request_does_not_demote_a_rule() -> None:
    """다른 주제의 편집 요청은 기존 규칙을 내리지 않는다(토큰 교집합 규칙이 여기서는 작동한다)."""
    assert (
        _constraint_status(("네트워크 사용은 금지합니다", "이 파일 좀 변경해줘"), "네트워크 사용은 금지합니다")
        == "active"
    )


# ── 알려진 결함 (측정 문서 §3에 기록됨) ──────────────────────────────────


@pytest.mark.xfail(
    strict=True,
    reason="측정 §3.1: 사전 밖 바꿔쓰기 12/12 누락 — 어휘 확장 카드에서 닫는다(닫으면 이 xfail 이 예상 밖 통과로 알려준다).",
)
@pytest.mark.parametrize("case", PARAPHRASES, ids=[c.text[:28] for c in PARAPHRASES])
def test_natural_paraphrases_should_also_be_structured(case: Any) -> None:
    """같은 뜻의 자연어 표현도 규칙으로 구조화돼야 한다(현재는 전부 누락)."""
    assert _kind(case.text) == case.expected


@pytest.mark.xfail(
    strict=True,
    reason="측정 §3.1: 부분 문자열 매칭 — 'mustard'/'blocking' 같은 잡담이 규칙으로 승격된다.",
)
@pytest.mark.parametrize("case", FALSE_POSITIVES, ids=[c.text[:28] for c in FALSE_POSITIVES])
def test_ordinary_chatter_should_not_become_a_constraint(case: Any) -> None:
    """사전 단어가 스친 잡담은 규칙이 아니어야 한다(승격되면 프롬프트 오염)."""
    assert _kind(case.text) is None


@pytest.mark.xfail(
    strict=True,
    reason="측정 §3.3 피해 ②: 'instead'+토큰 교집합으로 상시 규칙이 편집 지시에 무효화된다(렌더 블록에서 사라진다).",
)
def test_standing_rule_is_not_demoted_by_an_edit_instruction() -> None:
    """상시 규칙은 편집 지시 한 마디로 내려가지 않아야 한다(내려가면 정책이 조용히 사라진다)."""
    assert (
        _constraint_status(
            ("Always keep the deploy rule", "Use instead the new deploy config"), "Always keep the deploy rule"
        )
        == "active"
    )


@pytest.mark.xfail(
    strict=True,
    reason="측정 §3.3 피해 ①: approval cue 8종 밖의 승인 규칙('확인해줘')이 아예 구조화되지 않는다.",
)
def test_approval_rule_phrased_outside_the_lexicon_is_structured() -> None:
    """‘변경 전에는 먼저 확인해줘’ 같은 승인 규칙도 남아야 한다(현재는 생성조차 되지 않는다)."""
    assert _constraint_status(("변경 전에는 먼저 확인해줘",), "변경 전에는 먼저 확인해줘") == "active"
