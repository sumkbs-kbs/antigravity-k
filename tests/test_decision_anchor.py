"""DecisionAnchor 단위 테스트 — 핵심 합의 앵커 시스템."""

from collections.abc import Callable
from typing import cast

from antigravity_k.engine.decision_anchor import DecisionAnchor


class TestDecisionAnchorAdd:
    def test_add_returns_anchor_id(self):
        da = DecisionAnchor()
        anchor_id = da.add("DB 스키마는 A 방식으로 확정")
        assert len(anchor_id) == 8
        assert da.count == 1

    def test_add_strips_decision(self):
        da = DecisionAnchor()
        _ = da.add("  Python 3.12 사용  ")
        assert da.anchors[0].decision == "Python 3.12 사용"

    def test_add_clamps_priority(self):
        da = DecisionAnchor()
        _ = da.add("결정 A", priority=99)
        _ = da.add("결정 B", priority=-5)
        assert da.anchors[0].priority == 10
        assert da.anchors[1].priority == 1

    def test_add_defaults(self):
        da = DecisionAnchor()
        _ = da.add("결정 A")
        anchor = da.anchors[0]
        assert anchor.category == "general"
        assert anchor.priority == 5
        assert anchor.source == "user"

    def test_add_evicts_lowest_priority_when_full(self):
        da = DecisionAnchor()
        for i in range(10):
            _ = da.add(f"결정 {i}", priority=5)
        new_id = da.add("새로운 중요 결정", priority=10)
        assert da.count == DecisionAnchor.MAX_ANCHORS
        decisions = [a.decision for a in da.anchors]
        assert "결정 0" not in decisions  # 최저 우선순위 중 가장 오래된 앵커 퇴출
        assert any(a.anchor_id == new_id for a in da.anchors)

    def test_add_keeps_new_anchor_even_when_lowest_priority(self):
        da = DecisionAnchor()
        for i in range(10):
            _ = da.add(f"결정 {i}", priority=5)
        _ = da.add("낮은 우선순위 신규 앵커", priority=1)
        assert da.count == DecisionAnchor.MAX_ANCHORS
        assert any(a.decision == "낮은 우선순위 신규 앵커" for a in da.anchors)
        assert all(a.decision != "결정 0" for a in da.anchors)


class TestDecisionAnchorRemove:
    def test_remove_existing_returns_true(self):
        da = DecisionAnchor()
        anchor_id = da.add("결정 A")
        assert da.remove(anchor_id) is True
        assert da.count == 0

    def test_remove_missing_returns_false(self):
        da = DecisionAnchor()
        assert da.remove("missing") is False


class TestDecisionAnchorClear:
    def test_clear_empties(self):
        da = DecisionAnchor()
        _ = da.add("결정 A")
        _ = da.add("결정 B")
        da.clear()
        assert da.count == 0


class TestDecisionAnchorInject:
    def test_no_anchors_returns_same_messages(self):
        da = DecisionAnchor()
        messages = [{"role": "system", "content": "sys"}, {"role": "user", "content": "u"}]
        assert da.inject_into_messages(messages) == messages

    def test_injects_after_first_system_message(self):
        da = DecisionAnchor()
        _ = da.add("DB 스키마는 A 방식으로 확정")
        messages = [
            {"role": "system", "content": "sys1"},
            {"role": "user", "content": "u1"},
        ]
        result = da.inject_into_messages(messages)
        assert result[0] == messages[0]
        assert result[1]["role"] == "system"
        assert "[DECISION ANCHORS" in result[1]["content"]
        assert "DB 스키마는 A 방식으로 확정" in result[1]["content"]
        assert result[2] == messages[1]

    def test_injects_at_start_when_no_system_message(self):
        da = DecisionAnchor()
        _ = da.add("결정 A")
        messages = [{"role": "user", "content": "u1"}]
        result = da.inject_into_messages(messages)
        assert result[0]["role"] == "system"
        assert result[1] == messages[0]

    def test_anchors_sorted_by_priority_desc_in_block(self):
        da = DecisionAnchor()
        _ = da.add("낮은 우선순위 결정", priority=1)
        _ = da.add("높은 우선순위 결정", priority=10)
        result = da.inject_into_messages([{"role": "system", "content": "sys"}])
        block = cast(str, result[1]["content"])
        assert block.index("높은 우선순위 결정") < block.index("낮은 우선순위 결정")


class TestDecisionAnchorAutoExtract:
    def test_korean_decision_pattern(self):
        da = DecisionAnchor()
        result = da.auto_extract("DB 스키마는 A 방식으로 확정", "")
        # (?:로|으로)는 "로"가 우선 매칭되어 "으"가 후보에 포함됨 — 원본 패턴 동작
        assert result == {"decision": "DB 스키마는 A 방식으", "category": "general"}

    def test_korean_progress_pattern(self):
        da = DecisionAnchor()
        result = da.auto_extract("백엔드는 FastAPI 프레임워크로 진행", "")
        assert result == {"decision": "백엔드는 FastAPI", "category": "general"}

    def test_korean_decision_marker(self):
        da = DecisionAnchor()
        result = da.auto_extract("결정: API 응답 형식은 JSON으로 통일한다", "")
        assert result == {"decision": "API 응답 형식은 JSON으로 통일한다", "category": "convention"}

    def test_english_pattern_classifies_tooling(self):
        da = DecisionAnchor()
        result = da.auto_extract("Let's go with Python 3.12", "")
        assert result == {"decision": "Python 3.12", "category": "tooling"}

    def test_detects_decision_in_assistant_message(self):
        da = DecisionAnchor()
        result = da.auto_extract("뭐로 진행할까요?", "FastAPI로 하겠습니다")
        assert result == {"decision": "FastAPI", "category": "general"}

    def test_dedupe_existing_anchor_returns_none(self):
        da = DecisionAnchor()
        _ = da.add("DB 스키마는 A 방식")
        assert da.auto_extract("DB 스키마는 A 방식으로 확정", "") is None

    def test_too_short_candidate_ignored(self):
        da = DecisionAnchor()
        assert da.auto_extract("감사로 하자", "") is None

    def test_no_match_returns_none(self):
        da = DecisionAnchor()
        assert da.auto_extract("오늘 날씨가 정말 좋네요", "네, 그렇네요.") is None

    def test_extract_then_add_flow(self):
        da = DecisionAnchor()
        result = da.auto_extract("결정: Python 3.12 사용", "")
        assert result is not None
        _ = da.add(result["decision"], category=result["category"], source="auto")
        assert da.count == 1
        assert da.anchors[0].category == "tooling"
        assert da.anchors[0].source == "auto"


class TestDecisionAnchorClassifyCategory:
    def test_architecture(self):
        assert _classify_category("클린 아키텍처로 진행") == "architecture"

    def test_tooling(self):
        assert _classify_category("Python 3.12 사용") == "tooling"

    def test_convention(self):
        assert _classify_category("코드 스타일은 Black으로 통일") == "convention"

    def test_scope(self):
        assert _classify_category("MVP 범위로 진행") == "scope"

    def test_general(self):
        assert _classify_category("이름은 뭐든 좋다") == "general"


class TestDecisionAnchorRenderAndStats:
    def test_render_status_empty(self):
        da = DecisionAnchor()
        assert da.render_status() == "🔓 활성 결정 앵커 없음"

    def test_render_status_with_anchors(self):
        da = DecisionAnchor()
        _ = da.add("결정 A", priority=1)
        _ = da.add("결정 B", priority=10)
        status = da.render_status()
        assert "🔒 활성 결정 앵커: 2개" in status
        assert status.index("결정 B") < status.index("결정 A")  # 우선순위 내림차순

    def test_get_stats(self):
        da = DecisionAnchor()
        _ = da.add("결정 A", category="tooling", source="user")
        _ = da.add("결정 B", category="tooling", source="auto")
        _ = da.add("결정 C", category="general", source="auto")
        stats = da.get_stats()
        assert stats["total_anchors"] == 3
        assert stats["max_anchors"] == DecisionAnchor.MAX_ANCHORS
        assert stats["categories"] == {"tooling": 2, "general": 1}
        assert stats["source_breakdown"] == {"user": 1, "auto": 2}


def _classify_category(decision: str) -> str:
    classify = cast(Callable[[str], str], getattr(DecisionAnchor, "_classify_category"))
    return classify(decision)
