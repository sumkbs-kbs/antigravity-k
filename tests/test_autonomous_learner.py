"""테스트: AutonomousLearner — 지식 갭 감지·키워드 폴백.
============================================
should_learn 트리거 임계값, analyze_knowledge_gap의 LLM 폴백,
키워드 기반 쿼리 생성을 검증한다.
"""

import json
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.autonomous_learner import AutonomousLearner, KnowledgeGap


@pytest.fixture
def learner():
    return AutonomousLearner(model_manager=None, ki_engine=None)


# ─── should_learn ────────────────────────────────────────────────


class TestShouldLearn:
    def test_short_conversational_question_skipped(self, learner):
        assert learner.should_learn("안녕하세요") is False

    def test_three_trigger_matches_trigger_learn(self, learner):
        task = "최신 라이브러리 설치 방법을 알려줘. 프레임워크 문서도 필요해"

        assert learner.should_learn(task) is True

    def test_url_presence_triggers(self, learner):
        # 80자 이상 + URL → 트리거
        task = (
            "다음 공식 문서를 참고해서 통합 가이드를 작성해줘: "
            "https://example.com/very/long/documentation/path 그리고 요약본도 만들어줘"
        )
        assert learner.should_learn(task) is True

    def test_question_with_two_triggers_and_length(self, learner):
        task = (
            "api와 library를 어떻게 연결하나요? "
            "두 패키지의 호환성과 설정 방법을 포함해서 충분히 긴 질문을 덧붙입니다."
        )
        assert learner.should_learn(task) is True


# ─── analyze_knowledge_gap ────────────────────────────────────────


class TestAnalyzeKnowledgeGap:
    def test_llm_failure_falls_back_to_keywords(self):
        manager = MagicMock()
        manager.generate.side_effect = RuntimeError("llm down")
        learner = AutonomousLearner(model_manager=manager)

        gaps = learner.analyze_knowledge_gap("FastAPI 와 Pydantic 을 사용한 프로젝트")

        assert gaps and all(isinstance(g, KnowledgeGap) for g in gaps)

    def test_llm_success_parses_gaps(self, monkeypatch):
        ollama_response = json.dumps(
            {
                "response": '[{"topic": "Redis 캐싱", "reason": "성능 최적화 필요",'
                ' "search_queries": ["Redis caching"]}]'
            }
        )

        class FakeResp:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

            def read(self):
                return ollama_response.encode()

        monkeypatch.setattr(
            "antigravity_k.engine.autonomous_learner.safe_urlopen",
            lambda req, timeout=30: FakeResp(),
        )
        learner = AutonomousLearner(model_manager=MagicMock())

        gaps = learner.analyze_knowledge_gap("캐싱 전략 세워줘")

        assert len(gaps) == 1
        assert gaps[0].topic == "Redis 캐싱"


class TestKeywordFallback:
    def test_quoted_terms_become_topics(self, learner):
        gaps = learner._analyze_with_keywords('"Docker Compose" 활용법을 알려줘')

        assert any(g.topic == "Docker Compose" for g in gaps)
        assert any("tutorial" in q for g in gaps for q in g.search_queries)

    def test_tech_terms_combined_into_single_gap(self, learner):
        gaps = learner._analyze_with_keywords("FastAPI 와 SQLAlchemy 연동")

        combined = [g for g in gaps if "FastAPI" in g.topic]
        assert combined

    def test_fallback_when_no_signals(self, learner):
        gaps = learner._analyze_with_keywords("일반적인 텍스트")

        assert len(gaps) == 1
        assert gaps[0].reason == "일반 태스크 학습"

    def test_max_three_gaps(self, learner):
        text = '"a" 와 "b" 그리고 "c" 또 "d" 와 "e" 학습 대상이 많다 FastAPI Pydantic SQLAlchemy Docker Redis'

        gaps = learner._analyze_with_keywords(text)

        assert len(gaps) <= 3
