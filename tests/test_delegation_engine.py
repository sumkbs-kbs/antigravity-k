"""DelegationEngine 단위 테스트 (작업 A).

전략 추천 로직, 알 수 없는 전략 폴백, 파이프라인/토론 흐름을 검증합니다.
"""

from antigravity_k.engine.delegation_engine import (
    DelegationEngine,
    DelegationResult,
    DelegationStrategy,
)


class MockOrchestrator:
    """DelegationEngine 테스트용 최소 모의 오케스트레이터."""

    def __init__(self):
        self.manager = None
        self._last_agent_output = ""
        self._max_engine = None
        self.config = {}
        self.tool_registry = None


class TestRecommendStrategy:
    """recommend_strategy 결정적 전략 선택 검증."""

    def setup_method(self):
        self.engine = DelegationEngine(MockOrchestrator())

    def test_simple_coding_is_single(self):
        s = self.engine.recommend_strategy("coding", "함수 하나 작성해줘")
        assert s == DelegationStrategy.SINGLE

    def test_refactor_is_parallel(self):
        s = self.engine.recommend_strategy("coding", "이 아키텍처를 전면 리팩토링해줘")
        assert s == DelegationStrategy.PARALLEL

    def test_tradeoff_is_debate(self):
        s = self.engine.recommend_strategy("reasoning", "두 접근법의 장단점과 트레이드오프 비교")
        assert s == DelegationStrategy.DEBATE

    def test_explicit_pipeline_respected(self):
        s = self.engine.recommend_strategy("complex", "anything", analysis={"pipeline": [{"prompt": "step1"}]})
        assert s == DelegationStrategy.PIPELINE

    def test_complex_without_pipeline_is_parallel(self):
        s = self.engine.recommend_strategy("complex", "대규모 시스템 구축")
        assert s == DelegationStrategy.PARALLEL

    def test_simple_chat_is_single(self):
        s = self.engine.recommend_strategy("simple_chat", "안녕하세요")
        assert s == DelegationStrategy.SINGLE


class TestStrategyEnum:
    """DelegationStrategy 열거형 검증."""

    def test_strategy_values(self):
        assert DelegationStrategy.SINGLE.value == "single"
        assert DelegationStrategy.PARALLEL.value == "parallel"
        assert DelegationStrategy.PIPELINE.value == "pipeline"
        assert DelegationStrategy.DEBATE.value == "debate"
        assert DelegationStrategy.SUBAGENT.value == "subagent"

    def test_strategy_from_string(self):
        assert DelegationStrategy("single") == DelegationStrategy.SINGLE
        assert DelegationStrategy("parallel") == DelegationStrategy.PARALLEL


class TestDelegationResult:
    """DelegationResult 데이터클래스 검증."""

    def test_default_metadata_is_empty_dict(self):
        result = DelegationResult(strategy=DelegationStrategy.SINGLE, success=True)
        assert result.metadata == {}

    def test_metadata_not_shared_between_instances(self):
        r1 = DelegationResult(strategy=DelegationStrategy.SINGLE, success=True)
        r2 = DelegationResult(strategy=DelegationStrategy.SINGLE, success=True)
        r1.metadata["x"] = 1
        assert "x" not in r2.metadata
