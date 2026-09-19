"""Tests for CognitiveLoop — Dashboard용 CognitiveAdaptation 이벤트 발행."""

from __future__ import annotations

import pytest

from antigravity_k.engine.cognitive_loop import CognitiveLoop


class TestCognitiveAdaptationEvent:
    """adapt_strategy가 전략 적응 시 CognitiveAdaptation 이벤트를 발행한다."""

    @pytest.mark.asyncio
    async def test_adapt_strategy_publishes_cognitive_adaptation(
        self,
        tmp_path: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        published: list[tuple[str, dict[str, object]]] = []

        class _FakeBus:
            def publish(self, event_name: str, **kwargs: object) -> None:
                published.append((event_name, kwargs))

        monkeypatch.setattr("antigravity_k.engine.event_bus.global_event_bus", _FakeBus())

        loop = CognitiveLoop(project_root=str(tmp_path))
        loop._step_history = [
            {"tool": "run_bash_command", "grade": "F", "passed": False, "issues": ["timeout"]},
            {"tool": "run_bash_command", "grade": "F", "passed": False, "issues": ["timeout"]},
        ]

        adaptation = await loop.adapt_strategy("테스트 작업", None)

        assert adaptation is not None, "반복 실패 시 적응 프롬프트가 생성되어야 한다"
        assert published, "CognitiveAdaptation 이벤트가 발행되어야 한다"
        event_name, kwargs = published[0]
        assert event_name == "CognitiveAdaptation"
        assert "reason" in kwargs and kwargs["reason"]
        assert kwargs["adaptation"] == adaptation

    @pytest.mark.asyncio
    async def test_no_adaptation_no_event(
        self,
        tmp_path: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        published: list[tuple[str, dict[str, object]]] = []

        class _FakeBus:
            def publish(self, event_name: str, **kwargs: object) -> None:
                published.append((event_name, kwargs))

        monkeypatch.setattr("antigravity_k.engine.event_bus.global_event_bus", _FakeBus())

        loop = CognitiveLoop(project_root=str(tmp_path))
        loop._step_history = [{"tool": "read_file", "grade": "A", "passed": True, "issues": []}]

        adaptation = await loop.adapt_strategy("테스트 작업", None)

        assert adaptation is None
        assert all(name != "CognitiveAdaptation" for name, _ in published)
        assert all(name != "AntiPatternsDetected" for name, _ in published)


class TestAntiPatternsDetectedEvent:
    """adapt_strategy가 반복 실패 감지 시 AntiPatternsDetected 이벤트를 발행한다."""

    @pytest.mark.asyncio
    async def test_adapt_strategy_publishes_anti_patterns_detected(
        self,
        tmp_path: object,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        published: list[tuple[str, dict[str, object]]] = []

        class _FakeBus:
            def publish(self, event_name: str, **kwargs: object) -> None:
                published.append((event_name, kwargs))

        monkeypatch.setattr("antigravity_k.engine.event_bus.global_event_bus", _FakeBus())

        loop = CognitiveLoop(project_root=str(tmp_path))
        loop._step_history = [
            {"tool": "run_bash_command", "grade": "F", "passed": False, "issues": ["timeout"]},
            {"tool": "run_bash_command", "grade": "F", "passed": False, "issues": ["timeout"]},
        ]

        adaptation = await loop.adapt_strategy("테스트 작업", None)

        assert adaptation is not None, "반복 실패 시 적응 프롬프트가 생성되어야 한다"
        names = [name for name, _ in published]
        assert "AntiPatternsDetected" in names
        anti_kwargs = next(kwargs for name, kwargs in published if name == "AntiPatternsDetected")
        assert anti_kwargs["tools"] == ["run_bash_command"]
        patterns = anti_kwargs["patterns"]
        assert isinstance(patterns, list) and patterns, "누적 실패 패턴이 함께 전달되어야 한다"
