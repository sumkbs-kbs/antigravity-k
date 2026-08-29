"""Unit tests for PromptCompiler."""

import tempfile

from antigravity_k.engine.prompt_compiler import PromptCompiler


def test_prompt_compilation_with_golden_patterns():
    with tempfile.TemporaryDirectory() as tmpdir:
        compiler = PromptCompiler(prompts_dir=tmpdir)

        compiler.record_trajectory(
            role="worker",
            user_prompt="Write an async HTTP client",
            successful_action="use httpx.AsyncClient with context manager",
            failing_action="use blocking requests",
            lesson="Never use blocking requests in async def",
        )

        base = "You are a professional software engineer."
        compiled = compiler.compile_optimized_prompt("worker", base)

        assert "role: worker" in compiled
        assert "httpx.AsyncClient" in compiled
        assert "use blocking requests" in compiled
        assert "Never use blocking requests" in compiled

        saved_path = compiler.save_compiled_prompt("worker", compiled)
        assert saved_path.exists()
