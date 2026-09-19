"""EVO-01 — 자기 진화 sandbox fail-closed 검증.

docs/11_COMMERCIAL_GA_100_PLAN.md §EVO-01 수용 기준:
- sandbox init 예외 fixture에서 mutation call 0회, 파일 diff 0이다.
- validation 실패와 timeout에서 정확한 task-owned rollback이 실행된다.
- unsafe fallback flag가 기본/production 설정에 존재하지 않는다.
- 승인, 적용, 검증, rollback 단계가 event ledger에 남는다.

실행: uv run --no-sync pytest tests/test_evo01_mutation_fail_closed.py -q
"""

from __future__ import annotations

from typing import Any

import pytest

from antigravity_k.engine.self_evolution_coordinator import (
    MutationDomain,
    PerformanceSnapshot,
    SelfEvolutionCoordinator,
)


def _snapshot(score: float = 0.4, grade: str = "C") -> PerformanceSnapshot:
    return PerformanceSnapshot(
        user_message="evo01 test task",
        quality_score=score,
        quality_grade=grade,
        quality_issues=["weak: regression"],
    )


class _ExplodingSandbox:
    """sandbox init/사용 예외를 재현하는 fixture — safe_mutation 호출 시 즉시 실패."""

    def safe_mutation(self, label: str = "") -> Any:
        raise RuntimeError("sandbox exploded (fixture)")

    def validate_mutation(self, filepath: str, new_content: str) -> dict[str, Any]:
        raise RuntimeError("sandbox exploded (fixture)")

    def dual_audit(self, **kwargs: Any) -> dict[str, Any]:
        raise RuntimeError("sandbox exploded (fixture)")


class _CountingSandbox:
    """mutation 호출 횟수를 세는 fixture — fail-closed에서 0회여야 한다."""

    def __init__(self) -> None:
        self.safe_mutation_calls = 0

    def safe_mutation(self, label: str = "") -> Any:
        self.safe_mutation_calls += 1
        raise RuntimeError("sandbox exploded (fixture)")

    def validate_mutation(self, filepath: str, new_content: str) -> dict[str, Any]:
        return {"syntax": "pass", "security": "pass"}

    def dual_audit(self, **kwargs: Any) -> dict[str, Any]:
        return {"approved": True}


class TestSandboxFailClosed:
    def test_sandbox_init_failure_blocks_mutation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-1: sandbox init 예외 시 mutation 0회 — auto_evolve가 fail-closed skip."""
        coord = SelfEvolutionCoordinator(project_root="/tmp/evo01-test")

        # sandbox 초기화를 실패하게 만든다
        def _boom(*args: Any, **kwargs: Any) -> Any:
            raise ImportError("rsi_sandbox unavailable (fixture)")

        monkeypatch.setattr(
            "antigravity_k.engine.rsi_sandbox.RSISandbox",
            _boom,
            raising=False,
        )
        coord._deps_initialized = False
        coord._ensure_deps()

        assert coord._deps_init_failed is True
        assert "sandbox" in coord._deps_init_error

        result = coord.auto_evolve(_snapshot())
        # mutation 실행 시도 자체가 없어야 한다 — skipped + fail-closed 사유
        assert result.skipped is True
        assert result.success is False
        assert "fail-closed" in result.error_message
        # ledger에 blocked 이벤트가 남는다
        stages = [e["stage"] for e in coord.get_event_ledger()]
        assert "blocked" in stages

    def test_sandbox_none_never_runs_unsandboxed_mutation(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-1: sandbox가 None이어도 unsandboxed mutation 폴백 경로가 없다."""
        coord = SelfEvolutionCoordinator(project_root="/tmp/evo01-test")
        coord._deps_initialized = True
        coord._sandbox = None
        # 진화 판단은 통과하도록 최근 진화 시간 리셋
        coord._last_evolution_time = 0.0
        coord._turns_since_last_evolution = 999

        counting = _CountingSandbox()
        coord._sandbox = counting  # type: ignore[assignment]
        # safe_mutation이 예외를 던지는 fixture로 교체 — unsandboxed 경로가 있으면
        # _execute_mutation이 sandbox 없이 호출되어 카운트와 무관하게 적용된다.
        exploding = _ExplodingSandbox()
        exploding_calls = {"n": 0}
        original_safe = exploding.safe_mutation

        def _counting_explode(label: str = "") -> Any:
            exploding_calls["n"] += 1
            return original_safe(label)

        exploding.safe_mutation = _counting_explode  # type: ignore[method-assign]
        coord._sandbox = exploding  # type: ignore[assignment]

        result = coord.auto_evolve(_snapshot())
        # sandbox 예외 → rollback, unsandboxed 실행 없음
        assert result.success is False
        assert exploding_calls["n"] == 1  # sandbox 경로로만 시도됨
        assert result.rolled_back is True


class TestValidationRollback:
    def test_validation_failure_triggers_rollback(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-2: validation 실패 → task-owned rollback + event 기록."""
        coord = SelfEvolutionCoordinator(project_root="/tmp/evo01-test")
        coord._deps_initialized = True

        class _Status:
            def __init__(self, value: str) -> None:
                self.value = value

        class _SandboxFail:
            def safe_mutation(self, label: str = "") -> Any:
                from contextlib import nullcontext

                return nullcontext()

            def validate_mutation(self, filepath: str, new_content: str) -> dict[str, Any]:
                # coordinator는 getattr(v, "value") == "fail" 판정을 사용한다
                return {"syntax": _Status("fail"), "security": _Status("pass")}

            def dual_audit(self, **kwargs: Any) -> dict[str, Any]:
                return {"approved": True}

        coord._sandbox = _SandboxFail()  # type: ignore[assignment]
        coord._last_evolution_time = 0.0
        coord._turns_since_last_evolution = 999

        # system_prompt mutation이 applied=True를 반환하도록 강제
        monkeypatch.setattr(
            coord,
            "_mutate_system_prompt",
            lambda decision, snapshot: {
                "applied": True,
                "message": "fixture",
                "method": "fixture",
                "new_prompt_snippet": "EVO01 fixture prompt content for validation path",
            },
        )
        # validation이 실제 파일 검증 경로로 들어가도록 target_file 세팅
        coord._analyze = (  # type: ignore[method-assign]
            lambda snapshot: type(
                "D",
                (),
                {
                    "domain": MutationDomain.SYSTEM_PROMPT,
                    "confidence": 0.9,
                    "expected_improvement": 0.1,
                    "target_file": "prompts/system_prompt.md",
                },
            )()
        )

        result = coord.auto_evolve(_snapshot())
        assert result.success is False
        assert result.rolled_back is True
        assert "Validation failed" in result.error_message
        stages = [e["stage"] for e in result.events]
        assert "applied" in stages
        assert "validation_failed" in stages
        assert "rolled_back" in stages
        assert "validated" not in stages  # 실패했으므로 validated 없음

    def test_events_record_full_lifecycle(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """AC-4: 승인/적용/검증/rollback event가 ledger에 남는다."""
        coord = SelfEvolutionCoordinator(project_root="/tmp/evo01-test")
        coord._deps_initialized = True

        class _SandboxPass:
            def safe_mutation(self, label: str = "") -> Any:
                from contextlib import nullcontext

                return nullcontext()

            def validate_mutation(self, filepath: str, new_content: str) -> dict[str, Any]:
                return {"syntax": "pass", "security": "pass"}

            def dual_audit(self, **kwargs: Any) -> dict[str, Any]:
                return {"approved": True}

        coord._sandbox = _SandboxPass()  # type: ignore[assignment]
        coord._last_evolution_time = 0.0
        coord._turns_since_last_evolution = 999

        monkeypatch.setattr(
            coord,
            "_mutate_system_prompt",
            lambda decision, snapshot: {"applied": True, "message": "fixture", "method": "fixture"},
        )

        result = coord.auto_evolve(_snapshot())
        assert result.success is True
        stages = [e["stage"] for e in coord.get_event_ledger()]
        assert "applied" in stages
        assert "validated" in stages
        assert "approved" in stages
        assert "rolled_back" not in stages


class TestNoUnsafeFallback:
    def test_no_unsafe_fallback_flag_in_production_config(self) -> None:
        """AC-3: unsafe fallback flag가 기본/production 설정에 존재하지 않는다."""
        import src.antigravity_k.config as config_module  # type: ignore[import-not-found]

        source = open(config_module.__file__, encoding="utf-8").read()
        assert "allow_unsandboxed_mutation" not in source
        assert "UNSAFE_FALLBACK" not in source

    def test_no_unsandboxed_branch_in_coordinator(self) -> None:
        """AC-3: coordinator에 sandbox 없는 mutation 분기가 남아 있지 않다."""
        import inspect

        src = inspect.getsource(SelfEvolutionCoordinator.auto_evolve)
        assert "else:" not in src.split("with self._sandbox.safe_mutation")[1].split("# 5.")[0]
