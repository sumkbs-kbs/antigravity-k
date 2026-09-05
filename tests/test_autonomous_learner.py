from __future__ import annotations

"""테스트: AutonomousLearner — 지식 갭 감지·키워드 폴백.
============================================
should_learn 트리거 임계값, analyze_knowledge_gap의 LLM 폴백,
키워드 기반 쿼리 생성을 검증한다.
"""

import json
from collections.abc import Callable
from types import TracebackType
from typing import cast

import pytest

from antigravity_k.engine.autonomous_learner import AutonomousLearner, KnowledgeGap


class _FakeManager:
    def __init__(
        self,
        response: str | None = None,
        *,
        error: Exception | None = None,
        target: str = "detected-local-reasoning",
    ) -> None:
        self.response: str | None = response
        self.error: Exception | None = error
        self.target: str = target
        self.target_calls: list[tuple[str, str]] = []
        self.generate_calls: list[dict[str, object]] = []

    def get_target_for_role(self, role_name: str, *, default_role: str = "reasoning") -> str:
        self.target_calls.append((role_name, default_role))
        return self.target

    def generate(
        self,
        prompt: str,
        target: str,
        *,
        max_tokens: int,
        temperature: float,
    ) -> object:
        self.generate_calls.append(
            {
                "prompt": prompt,
                "target": target,
                "max_tokens": max_tokens,
                "temperature": temperature,
            }
        )
        if self.error is not None:
            raise self.error
        return self.response if self.response is not None else object()


class _FakeResponse:
    def __init__(self, body: bytes) -> None:
        self.body: bytes = body

    def __enter__(self) -> _FakeResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool:
        _ = (exc_type, exc_value, traceback)
        return False

    def read(self) -> bytes:
        return self.body


@pytest.fixture
def learner() -> AutonomousLearner:
    return AutonomousLearner(model_manager=None, ki_engine=None)


def _keyword_analysis(learner: AutonomousLearner, text: str) -> list[KnowledgeGap]:
    method = cast(Callable[[str], list[KnowledgeGap]], getattr(learner, "_analyze_with_keywords"))
    return method(text)


# ─── should_learn ────────────────────────────────────────────────


class TestShouldLearn:
    def test_short_conversational_question_skipped(self, learner: AutonomousLearner):
        assert learner.should_learn("안녕하세요") is False

    def test_three_trigger_matches_trigger_learn(self, learner: AutonomousLearner):
        task = "최신 라이브러리 설치 방법을 알려줘. 프레임워크 문서도 필요해"

        assert learner.should_learn(task) is True

    def test_url_presence_triggers(self, learner: AutonomousLearner):
        # 80자 이상 + URL → 트리거
        task = (
            "다음 공식 문서를 참고해서 통합 가이드를 작성해줘: "
            "https://example.com/very/long/documentation/path 그리고 요약본도 만들어줘"
        )
        assert learner.should_learn(task) is True

    def test_question_with_two_triggers_and_length(self, learner: AutonomousLearner):
        task = (
            "api와 library를 어떻게 연결하나요? "
            "두 패키지의 호환성과 설정 방법을 포함해서 충분히 긴 질문을 덧붙입니다."
        )
        assert learner.should_learn(task) is True


# ─── analyze_knowledge_gap ────────────────────────────────────────


class TestAnalyzeKnowledgeGap:
    def test_llm_success_uses_managed_model_target(self):
        manager = _FakeManager(
            response='[{"topic":"Managed API","reason":"검증","search_queries":["managed api"]}]'
        )
        learner = AutonomousLearner(model_manager=manager)

        gaps = learner.analyze_knowledge_gap("최신 API 문서를 조사해줘")

        assert gaps[0].topic == "Managed API"
        assert manager.target_calls == [("knowledge_gap_analyzer", "reasoning")]
        assert len(manager.generate_calls) == 1
        assert manager.generate_calls[0]["target"] == "detected-local-reasoning"
        assert manager.generate_calls[0]["max_tokens"] == 512
        assert manager.generate_calls[0]["temperature"] == 0.3

    def test_llm_failure_falls_back_to_keywords(self):
        manager = _FakeManager(error=RuntimeError("llm down"))
        learner = AutonomousLearner(model_manager=manager)

        gaps = learner.analyze_knowledge_gap("FastAPI 와 Pydantic 을 사용한 프로젝트")

        assert gaps and all(isinstance(g, KnowledgeGap) for g in gaps)

    def test_llm_success_parses_gaps(self, monkeypatch: pytest.MonkeyPatch):
        ollama_response = json.dumps(
            {
                "response": '[{"topic": "Redis 캐싱", "reason": "성능 최적화 필요",'
                + ' "search_queries": ["Redis caching"]}]'
            }
        )

        def fake_urlopen(request: object, timeout: int = 30) -> _FakeResponse:
            _ = (request, timeout)
            return _FakeResponse(ollama_response.encode())

        monkeypatch.setattr(
            "antigravity_k.engine.autonomous_learner.safe_urlopen",
            fake_urlopen,
        )
        learner = AutonomousLearner(model_manager=_FakeManager())

        gaps = learner.analyze_knowledge_gap("캐싱 전략 세워줘")

        assert len(gaps) == 1
        assert gaps[0].topic == "Redis 캐싱"


class TestKeywordFallback:
    def test_quoted_terms_become_topics(self, learner: AutonomousLearner):
        gaps = _keyword_analysis(learner, '"Docker Compose" 활용법을 알려줘')

        assert any(g.topic == "Docker Compose" for g in gaps)
        assert any("tutorial" in q for g in gaps for q in g.search_queries)

    def test_tech_terms_combined_into_single_gap(self, learner: AutonomousLearner):
        gaps = _keyword_analysis(learner, "FastAPI 와 SQLAlchemy 연동")

        combined = [g for g in gaps if "FastAPI" in g.topic]
        assert combined

    def test_fallback_when_no_signals(self, learner: AutonomousLearner):
        gaps = _keyword_analysis(learner, "일반적인 텍스트")

        assert len(gaps) == 1
        assert gaps[0].reason == "일반 태스크 학습"

    def test_max_three_gaps(self, learner: AutonomousLearner):
        text = '"a" 와 "b" 그리고 "c" 또 "d" 와 "e" 학습 대상이 많다 FastAPI Pydantic SQLAlchemy Docker Redis'

        gaps = _keyword_analysis(learner, text)

        assert len(gaps) <= 3
