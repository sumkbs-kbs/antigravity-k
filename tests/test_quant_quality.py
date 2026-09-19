"""quant_quality 테스트 — dashboard/src/utils/quantQuality.ts와의 등급 일치 검증.

Phase 18: agk model list CLI가 대시보드 Model Hub 배지와 동일한 품질 등급을
표시하도록 하는 Python 측 매핑의 정합성을 잠근다.

Phase 46: 케이스 전부를 공유 conformance fixture(tests/fixtures/quant_quality_conformance.json)로
옮겨 TS/파이썬 쌍생 구현이 같은 케이스 셋을 검증하도록 한다 — 어느 한쪽이 어긋나면 동일 fixture 테스트가
양쪽에서 함께 실패해 드리프트를 즉시 드러낸다.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from antigravity_k.engine.quant_quality import LEVEL_ORDER, quant_quality

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "tests" / "fixtures" / "quant_quality_conformance.json"


@pytest.mark.parametrize(
    ("token", "expected_level", "expected_grade"),
    [
        # premium
        ("UD-Q8_K_XL", "premium", "P"),
        ("Q8_0", "premium", "P"),
        ("F16", "premium", "P"),
        ("BF16", "premium", "P"),
        ("8bit", "premium", "P"),
        # high
        ("Q6_K", "high", "H"),
        ("Q5_K_M", "high", "H"),
        ("6bit", "high", "H"),
        ("5bit", "high", "H"),
        # balanced
        ("UD-Q4_K_XL", "balanced", "B"),
        ("Q4_K_M", "balanced", "B"),
        ("IQ4_XS", "balanced", "B"),
        ("4bit", "balanced", "B"),
        ("q4_k_m", "balanced", "B"),  # 대소문자 무관
        # compact
        ("Q3_K_L", "compact", "C"),
        ("Q2_K", "compact", "C"),
        ("IQ2_M", "compact", "C"),
        ("IQ1_S", "compact", "C"),
        ("TQ1_0", "compact", "C"),
        ("2bit", "compact", "C"),
        ("3bit", "compact", "C"),
        # unknown
        ("", "unknown", "?"),
        (None, "unknown", "?"),
        ("Active", "unknown", "?"),
        ("N/A", "unknown", "?"),
        ("fused", "unknown", "?"),
    ],
)
def test_quant_quality_matches_dashboard_levels(token: str | None, expected_level: str, expected_grade: str) -> None:
    info = quant_quality(token)
    assert info.level == expected_level
    assert info.grade == expected_grade
    assert info.label  # 사용자 설명 항상 존재


def test_level_order_is_monotonic_quality_ranking() -> None:
    assert (
        LEVEL_ORDER["unknown"]
        < LEVEL_ORDER["compact"]
        < LEVEL_ORDER["balanced"]
        < LEVEL_ORDER["high"]
        < LEVEL_ORDER["premium"]
    )


def test_conformance_fixture_exists_and_is_wellformed() -> None:
    """fixture 자체의 형식 검증 — 케이스/서열/메타 3 섹션이 모두 있어야 한다."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert len(data["token_cases"]) >= 30
    assert data["grade_order"] == ["unknown", "compact", "balanced", "high", "premium"]
    assert set(data["grade_meta"]) == set(data["grade_order"])
    for case in data["token_cases"]:
        assert case["level"] in data["grade_order"], case


@pytest.mark.parametrize(
    ("token", "expected_level"),
    [tuple(case.values()) for case in json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["token_cases"]],
)
def test_python_matches_conformance_fixture(token: str | None, expected_level: str) -> None:
    """파이썬 구현이 공유 fixture의 모든 케이스와 일치 (TS 측 대응 테스트와 동일 셋)."""
    info = quant_quality(token)
    assert info.level == expected_level, f"token={token!r}"


def test_python_grade_meta_matches_fixture() -> None:
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    # 각 등급을 대표하는 실제 토큰으로 grade/label 대조 (level 이름 자체는 토큰이 아니다).
    representative_token = {
        "premium": "Q8_0",
        "high": "Q6_K",
        "balanced": "Q4_K_M",
        "compact": "Q2_K",
        "unknown": "",
    }
    for level, meta in data["grade_meta"].items():
        info = quant_quality(representative_token[level])
        assert info.level == level
        assert info.grade == meta["grade"], level
        assert info.label == meta["label"], level


def test_fixture_grade_order_matches_level_order() -> None:
    """fixture의 서열이 구현의 LEVEL_ORDER와 정확히 일치하는지 (같은 순서, 같은 상대 랭킹)."""
    data = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    order = data["grade_order"]
    assert order == list(LEVEL_ORDER), (order, list(LEVEL_ORDER))
    for lower, higher in zip(order, order[1:]):
        assert LEVEL_ORDER[lower] < LEVEL_ORDER[higher], (lower, higher)


def test_cli_quant_cell_renders_grade_letter_and_dash_for_unknown() -> None:
    """CLI 셸 헬퍼가 unknown을 — 로, 나머지를 토큰+등급으로 렌더링하는지 확인."""
    from antigravity_k.cli import _quant_cell  # noqa: PLC0415 — CLI 모듈 임포트 비용

    assert _quant_cell("") == "[dim]—[/dim]"
    assert _quant_cell("Active") == "[dim]—[/dim]"
    cell = _quant_cell("UD-Q8_K_XL")
    assert "UD-Q8_K_XL" in cell and "P" in cell and "[green]" in cell
    balanced = _quant_cell("4bit")
    assert "4bit" in balanced and "B" in balanced and "[magenta]" in balanced
