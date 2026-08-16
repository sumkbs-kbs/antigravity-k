from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, create_autospec

import pytest

from antigravity_k.engine.cognitive_loop import CognitiveLoop
from antigravity_k.engine.external_brain import BrainResponse
from antigravity_k.engine.failure_memory import FailureMemory
from antigravity_k.engine.tool_call_parser import ToolCall
from antigravity_k.engine.tool_loop import ToolLoopEngine


class TestExternalBrainRecovery:
    @pytest.mark.asyncio
    async def test_successful_delegation_records_failure_and_returns_advice(self):
        # Given: three tool failures and an external brain that returns actionable advice.
        failure_memory = create_autospec(FailureMemory, instance=True)
        router = MagicMock()
        router.send = AsyncMock(
            return_value=BrainResponse(
                text="Use a smaller reproducible command first.",
                source="local_critic",
                success=True,
            ),
        )
        loop = CognitiveLoop(
            failure_memory=failure_memory,
            external_brain_router=router,
        )
        failures = [
            {"tool": "run_bash_command", "issues": ["exit code 1"]},
            {"tool": "run_bash_command", "issues": ["exit code 1"]},
            {"tool": "run_bash_command", "issues": ["exit code 1"]},
        ]

        # When: the cognitive loop delegates the repeated failure.
        result = await loop.auto_delegate_to_external_brain("build the project", failures)

        # Then: advice is returned and the recovery is stored through the real memory contract.
        assert result is not None
        assert "Use a smaller reproducible command first." in result
        failure_memory.record.assert_called_once_with(
            tool="run_bash_command",
            error_text="3x_failure_run_bash_command",
            args_summary="build the project",
            fix_applied="external_brain_delegation_local_critic",
        )


class TestCognitiveToolRecovery:
    def test_nonzero_command_exit_is_recorded_as_failure(self):
        # Given: a command result with an explicit non-zero exit marker.
        loop = CognitiveLoop()

        # When: the cognitive verifier evaluates the command result.
        verification = loop.verify_tool_result(
            "run_bash_command",
            {"command": "exit 7"},
            "[exit_code=7]\ncommand failed",
        )

        # Then: the result contributes to recovery instead of being counted as success.
        assert verification["passed"] is False
        assert verification["grade"] == "F"

    @pytest.mark.asyncio
    async def test_three_command_failures_inject_recovery_guidance_into_tool_evidence(self):
        # Given: the production tool loop uses a real cognitive loop and a failing command tool.
        cognitive_loop = CognitiveLoop()
        guardrail = MagicMock()
        guardrail.before_call.return_value.allows_execution = True
        guardrail.after_call.return_value = MagicMock()
        context = SimpleNamespace(
            cognitive_loop=cognitive_loop,
            tool_executor=SimpleNamespace(
                execute_async=AsyncMock(return_value="[exit_code=7]\ncommand failed"),
            ),
            tool_guardrail=guardrail,
        )
        orch = SimpleNamespace(ctx=context)
        engine = ToolLoopEngine(orch)
        tool_call = ToolCall(name="run_bash_command", arguments={"command": "exit 7"})

        # When: the same command fails three times during one task.
        results = [await engine._run_tool_task_async(tool_call, "build the project") for _ in range(3)]

        # Then: the model-visible evidence includes a concrete strategy change.
        assert "Cognitive Adapt" in results[-1][3]

    def test_post_loop_reflection_uses_context_owned_cognitive_loop(self):
        # Given: a production-shaped orchestrator with cognition owned by its context.
        cognitive_loop = MagicMock()
        context = SimpleNamespace(cognitive_loop=cognitive_loop, quality_gate=None)
        engine = ToolLoopEngine(SimpleNamespace(ctx=context))

        # When: the tool loop completes its post-run checks.
        list(engine._post_loop_checks([], "code", "completed", "build the project"))

        # Then: the task outcome is reflected even without a duplicate orchestrator attribute.
        cognitive_loop.reflect.assert_called_once_with("build the project", "completed")
