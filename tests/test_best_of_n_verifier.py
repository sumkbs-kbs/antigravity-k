"""Unit tests for BestOfNVerifier (execution-verified best-of-N sampler)."""

import sys
from pathlib import Path
from typing import Any, cast

from antigravity_k.engine.best_of_n_verifier import (
    BestOfNVerifier,
    VerificationOutcome,
    budget_to_n_samples,
    extract_code,
    make_command_verifier,
)


def _gen_factory(outputs: list[str]):
    calls = {"n": 0}

    def gen(prompt: str, **kwargs) -> str:
        idx = min(calls["n"], len(outputs) - 1)
        calls["n"] += 1
        return outputs[idx]

    return gen, calls


class TestExtractCode:
    def test_extracts_fenced_code(self):
        text = "설명입니다\n```python\nprint('hi')\n```\n끝"
        assert extract_code(text) == "print('hi')"

    def test_prefers_language_hinted_fence(self):
        text = "```js\nconsole.log(1)\n```\n```python\nprint(1)\n```"
        assert extract_code(text, language_hint="python") == "print(1)"

    def test_returns_raw_text_without_fences(self):
        assert extract_code("plain code") == "plain code"

    def test_empty_input(self):
        assert extract_code("") == ""


class TestCommandVerifier:
    def test_passing_command(self):
        verifier = make_command_verifier([sys.executable, "-c", "pass"])
        outcome = verifier("```python\nprint('ok')\n```")
        assert outcome.passed is True

    def test_failing_command_captures_last_error_line(self):
        verifier = make_command_verifier([sys.executable, "{file}"], language_hint="python")
        outcome = verifier("```python\nraise ValueError('boom-123')\n```")
        assert outcome.passed is False
        assert "boom-123" in outcome.detail

    def test_empty_candidate_fails_fast(self):
        verifier = make_command_verifier([sys.executable, "-c", "pass"])
        outcome = verifier("")
        assert outcome.passed is False
        assert outcome.detail == "empty candidate"


class TestBestOfNVerifier:
    def test_first_pass_wins_early_exit(self):
        outputs = [
            "```python\ndef broken():\n    syntax error\n```",
            "```python\nprint('good')\n```",
            "```python\nprint('also good')\n```",
        ]
        gen, calls = _gen_factory(outputs)
        engine = BestOfNVerifier(
            generate_fn=gen,
            verifier_fn=make_command_verifier([sys.executable, "{file}"]),
            n_samples=3,
        )
        trace = engine.run("fix it")
        assert trace.skipped is False
        assert trace.early_exit is True
        assert trace.selected_index == 1
        # 조기 종료: 세 번째 후보는 샘플링/검증되지 않는다
        assert trace.n_candidates == 2
        assert trace.passed_count == 1

    def test_all_fail_returns_best_effort_with_details(self):
        outputs = [
            "```python\nraise ValueError('first-fail')\n```",
            "```python\nraise ValueError('second-fail')\n```",
        ]
        gen, _ = _gen_factory(outputs)
        engine = BestOfNVerifier(
            generate_fn=gen,
            verifier_fn=make_command_verifier([sys.executable, "{file}"]),
            n_samples=2,
        )
        trace = engine.run("fix it")
        assert trace.skipped is False
        assert trace.passed_count == 0
        assert trace.selected != ""
        failed = [c for c in trace.candidates if c.verification and not c.verification.passed]
        assert len(failed) == 2
        details = [c.verification.detail for c in failed if c.verification is not None]
        assert any("ValueError" in detail for detail in details)

    def test_no_verifier_single_generation_contract(self):
        gen, calls = _gen_factory(["single answer"])
        engine = BestOfNVerifier(generate_fn=gen, n_samples=3)
        trace = engine.run("hello")
        assert trace.skipped is True
        assert trace.selected == "single answer"
        assert calls["n"] == 1

    def test_feedback_loop_retries_on_all_empty_candidates(self):
        outputs = ["", "", "```python\nprint('recovered')\n```"]
        gen, _ = _gen_factory(outputs)
        engine = BestOfNVerifier(
            generate_fn=gen,
            verifier_fn=make_command_verifier([sys.executable, "{file}"]),
            n_samples=2,
        )
        trace = engine.run("try", feedback_loop=True, max_feedback_rounds=3)
        assert trace.skipped is False
        assert trace.early_exit is True

    def test_temperature_spread_applied(self):
        temps_seen: list[float] = []

        def gen(prompt: str, **kwargs) -> str:
            temps_seen.append(kwargs.get("temperature", 0.0))
            return ""

        engine = BestOfNVerifier(generate_fn=gen, n_samples=3)
        engine.collect_candidates("p")
        assert len(set(temps_seen)) == 3

    def test_budget_mapping_clamps(self):
        assert budget_to_n_samples(1) == 1
        assert budget_to_n_samples(3) == 3
        assert budget_to_n_samples(99) == 5
        assert budget_to_n_samples(-2) == 1


class TestConfigMapping:
    def test_config_to_engine_kwargs_casts(self):
        from antigravity_k.engine.best_of_n_verifier import config_to_engine_kwargs

        kwargs = config_to_engine_kwargs({"n_samples": "4", "base_temperature": 0.6})
        assert kwargs["n_samples"] == 4
        assert kwargs["base_temperature"] == 0.6

    def test_invalid_values_ignored(self):
        from antigravity_k.engine.best_of_n_verifier import config_to_engine_kwargs

        kwargs = config_to_engine_kwargs({"n_samples": "not-a-number"})
        assert "n_samples" not in kwargs


def test_verification_outcome_defaults(tmp_path: Path):
    outcome = VerificationOutcome(passed=True)
    assert outcome.score == 1.0
    assert outcome.detail == ""


class TestModelManagerWiring:
    def _make_manager(self, amp_cfg: dict[str, object]):
        from antigravity_k.engine.model_manager import ModelManager

        class FakeRegistry:
            _raw = {"amplification": {"best_of_n": amp_cfg}}

        mgr = cast(Any, ModelManager.__new__(ModelManager))
        mgr._registry = FakeRegistry()
        return mgr

    def test_generate_best_of_n_early_exit_on_valid_candidate(self):
        calls: list[float] = []
        mgr = self._make_manager({"enabled": True, "n_samples": 3})

        def gen(prompt, target, **kw):
            temperature = kw.get("temperature")
            if isinstance(temperature, (int, float)):
                calls.append(float(temperature))
            return f"```python\nx = {len(calls)}\n```"

        mgr.generate = gen
        out = mgr.generate_best_of_n("fix", "qwen")
        assert out == "```python\nx = 1\n```"
        assert len(calls) == 1

    def test_disabled_config_falls_back_to_plain_generate(self):
        mgr = self._make_manager({"enabled": False})
        mgr.generate = lambda prompt, target, **kw: "plain-answer"
        assert mgr.generate_best_of_n("q", "m") == "plain-answer"

    def test_syntax_error_candidates_are_skipped(self):
        mgr = self._make_manager({"enabled": True, "n_samples": 2})
        outputs = iter(["```python\ndef broken(:\n```", "```python\nok = True\n```"])
        mgr.generate = lambda prompt, target, **kw: next(outputs)
        out = mgr.generate_best_of_n("fix", "qwen")
        assert out == "```python\nok = True\n```"

    def test_compute_budget_scales_samples_with_complexity(self):
        mgr = self._make_manager({"enabled": True, "n_samples": 1, "use_compute_budget": True})
        calls: list[str] = []
        outputs = iter(
            [
                "```python\ndef broken(:\n```",
                "```python\ndef also broken(:\n```",
                "```python\nok = True\n```",
            ]
        )

        def gen(prompt, target, **kw):
            calls.append(prompt)
            return next(outputs)

        mgr.generate = gen
        trace_out = mgr.generate_best_of_n("refactor the concurrency architecture across all services", "qwen")
        from antigravity_k.engine.best_of_n_verifier import budget_to_n_samples
        from antigravity_k.engine.test_time_compute_scaler import TestTimeComputeScaler

        budget = TestTimeComputeScaler.evaluate_budget("refactor the concurrency architecture across all services")
        assert len(calls) == budget_to_n_samples(budget.branching_factor)
        assert trace_out != ""


class TestWorktreeTestVerifier:
    def _tiny_git_repo(self, tmp_path: Path) -> Path:
        import subprocess as sp

        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args: str) -> None:
            sp.run(["git", *args], cwd=repo, check=True, capture_output=True)

        git("init", "-q")
        git("config", "user.email", "t@t.local")
        git("config", "user.name", "t")
        (repo / "app.py").write_text("VALUE = 1\n", encoding="utf-8")
        git("add", ".")
        git("commit", "-qm", "init")
        return repo

    def test_passing_candidate_in_worktree(self, tmp_path: Path):
        from antigravity_k.engine.best_of_n_verifier import make_worktree_test_verifier

        repo = self._tiny_git_repo(tmp_path)
        verifier = make_worktree_test_verifier(
            repo,
            apply_fn=lambda text, ws: True,
            test_command=["python3", "-c", "import sys; sys.exit(0)"],
        )
        outcome = verifier("candidate text")
        assert outcome.passed is True

    def test_failing_test_reports_last_error_line(self, tmp_path: Path):
        from antigravity_k.engine.best_of_n_verifier import make_worktree_test_verifier

        repo = self._tiny_git_repo(tmp_path)
        verifier = make_worktree_test_verifier(
            repo,
            apply_fn=lambda text, ws: True,
            test_command=["python3", "-c", "raise SystemExit('boom-xyz')"],
        )
        outcome = verifier("candidate text")
        assert outcome.passed is False
        assert "boom-xyz" in outcome.detail

    def test_unappliable_patch_short_circuits(self, tmp_path: Path):
        from antigravity_k.engine.best_of_n_verifier import make_worktree_test_verifier

        verifier = make_worktree_test_verifier(
            tmp_path,
            apply_fn=lambda text, ws: False,
            test_command=["python3", "-c", "pass"],
        )
        outcome = verifier("anything")
        assert outcome.passed is False
        assert outcome.detail == "patch not applicable"

    def test_tempdir_fallback_without_git(self, tmp_path: Path):
        from antigravity_k.engine.best_of_n_verifier import make_worktree_test_verifier

        plain = tmp_path / "plain"
        plain.mkdir()
        seen_kinds: list[bool] = []

        def apply_fn(text: str, ws: Path) -> bool:
            seen_kinds.append(ws.exists())
            return True

        verifier = make_worktree_test_verifier(
            plain,
            apply_fn=apply_fn,
            test_command=["python3", "-c", "import sys; sys.exit(0)"],
        )
        assert verifier("c").passed is True
        assert seen_kinds == [True]


class TestParseFileBlocks:
    def test_extracts_annotated_fence(self):
        from antigravity_k.engine.best_of_n_verifier import parse_file_blocks

        text = "설명\n```python app.py\nVALUE = 2\n```\n끝"
        assert parse_file_blocks(text) == {"app.py": "VALUE = 2\n"}

    def test_ignores_plain_fences_without_path(self):
        from antigravity_k.engine.best_of_n_verifier import parse_file_blocks

        assert parse_file_blocks("```python\nx = 1\n```") == {}

    def test_multiple_files(self):
        from antigravity_k.engine.best_of_n_verifier import parse_file_blocks

        text = "```python src/a.py\nX=1\n```\n```js lib/b.js\nlet y;\n```"
        blocks = parse_file_blocks(text)
        assert set(blocks) == {"src/a.py", "lib/b.js"}


class TestAnswerPatchVerifier:
    def _tiny_git_repo(self, tmp_path: Path) -> Path:
        import subprocess as sp

        repo = tmp_path / "repo"
        repo.mkdir()

        def git(*args):
            sp.run(["git", *args], cwd=repo, check=True, capture_output=True)

        git("init", "-q")
        git("config", "user.email", "t@t.local")
        git("config", "user.name", "t")
        (repo / "config_value.py").write_text("VALUE = 1\n", encoding="utf-8")
        (repo / "test_value.py").write_text(
            "from config_value import VALUE\n\n\ndef test_two():\n    assert VALUE == 2\n",
            encoding="utf-8",
        )
        (repo / "__init__.py").write_text("", encoding="utf-8")
        git("add", ".")
        git("commit", "-qm", "init")
        return repo

    def test_passing_patch_detected(self, tmp_path: Path):
        import sys as _sys

        from antigravity_k.engine.best_of_n_verifier import make_answer_patch_verifier

        repo = self._tiny_git_repo(tmp_path)
        verifier = make_answer_patch_verifier(
            repo, [_sys.executable, "-m", "pytest", "-q", "test_value.py"], timeout_sec=60
        )
        answer = "수정안:\n```python config_value.py\nVALUE = 2\n```"
        outcome = verifier(answer)
        assert outcome.passed is True

    def test_failing_patch_reports_reason(self, tmp_path: Path):
        import sys as _sys

        from antigravity_k.engine.best_of_n_verifier import make_answer_patch_verifier

        repo = self._tiny_git_repo(tmp_path)
        verifier = make_answer_patch_verifier(
            repo, [_sys.executable, "-m", "pytest", "-q", "test_value.py"], timeout_sec=60
        )
        answer = "```python config_value.py\nVALUE = 999\n```"
        outcome = verifier(answer)
        assert outcome.passed is False
        assert outcome.detail != ""

    def test_path_traversal_rejected(self, tmp_path: Path):
        from antigravity_k.engine.best_of_n_verifier import make_answer_patch_verifier

        repo = self._tiny_git_repo(tmp_path)
        outside_marker = tmp_path / "outside.txt"
        verifier = make_answer_patch_verifier(repo, ["python3", "-c", "pass"])
        answer = "```text ../evil.txt\npwned\n```"
        outcome = verifier(answer)
        assert outcome.passed is False
        assert not outside_marker.exists()


def test_parse_file_blocks_rejects_parent_traversal():
    from antigravity_k.engine.best_of_n_verifier import parse_file_blocks

    assert parse_file_blocks("```text ../evil.txt\npwned\n```") == {}
    assert parse_file_blocks("```python a/../../b.py\nx\n```") == {}
    # 정상 상대 경로는 유지
    assert "src/a.py" in parse_file_blocks("```python src/a.py\nx=1\n```")
