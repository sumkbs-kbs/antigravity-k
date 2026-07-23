"""Tests for ci_tools.py — TestRunnerTool, AutoLintTool, PRCreationTool."""

import os
import tempfile
from unittest.mock import MagicMock, patch

from antigravity_k.tools.ci_tools import AutoLintTool, PRCreationTool, TestRunnerTool

# ── TestRunnerTool._detect_test_framework ──────────────────────────────


class TestDetectTestFramework:
    """Tests for TestRunnerTool._detect_test_framework pure-logic (file-based detection)."""

    def test_detect_pytest_pyproject(self):
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pyproject.toml"), "w") as f:
                f.write('[tool.pytest]\nini_options = "test*.py"')
            result = tool._detect_test_framework(tmpdir)
            assert result == "python -m pytest -v --tb=short"

    def test_detect_pytest_ini(self):
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pytest.ini"), "w") as f:
                f.write("[pytest]\nminversion = 7.0")
            result = tool._detect_test_framework(tmpdir)
            assert result == "python -m pytest -v --tb=short"

    def test_detect_makefile(self):
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "Makefile"), "w") as f:
                f.write("test:\n\tpytest")
            result = tool._detect_test_framework(tmpdir)
            assert result == "make test"

    def test_detect_cargo(self):
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "Cargo.toml"), "w") as f:
                f.write('[package]\nname = "test"')
            result = tool._detect_test_framework(tmpdir)
            assert result == "cargo test"

    def test_detect_go_mod(self):
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "go.mod"), "w") as f:
                f.write("module example.com/test")
            result = tool._detect_test_framework(tmpdir)
            assert result == "go test ./..."

    def test_detect_npm_test(self):
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "package.json"), "w") as f:
                f.write('{"scripts": {"test": "jest"}}')
            result = tool._detect_test_framework(tmpdir)
            assert result == "npm test"

    def test_detect_vitest(self):
        """package.json with vitest without 'test' script key should match vitest."""
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "package.json"), "w") as f:
                f.write('{"devDependencies": {"vitest": "^1.0.0"}}')
            result = tool._detect_test_framework(tmpdir)
            assert result == "npx vitest run"

    def test_detect_vitest_from_deps(self):
        """package.json with vitest in devDependencies but no 'test' script."""
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "package.json"), "w") as f:
                f.write('{"devDependencies": {"vitest": "^1.0.0"}}')
            result = tool._detect_test_framework(tmpdir)
            assert result == "npx vitest run"

    def test_detect_mix_exs(self):
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "mix.exs"), "w") as f:
                f.write("defmodule Test do")
            result = tool._detect_test_framework(tmpdir)
            assert result == "mix test"

    def test_detect_setup_py(self):
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "setup.py"), "w") as f:
                f.write("from setuptools import setup")
            result = tool._detect_test_framework(tmpdir)
            assert result == "python -m pytest -v --tb=short"

    def test_detect_rspec_gemfile(self):
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "Gemfile"), "w") as f:
                f.write('gem "rspec"')
            result = tool._detect_test_framework(tmpdir)
            assert result == "bundle exec rspec"

    def test_detect_no_framework(self):
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = tool._detect_test_framework(tmpdir)
            assert result is None

    def test_detect_priority_order(self):
        """pyproject.toml should be detected before Makefile."""
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pyproject.toml"), "w") as f:
                f.write("[tool.pytest]")
            with open(os.path.join(tmpdir, "Makefile"), "w") as f:
                f.write("test:")
            result = tool._detect_test_framework(tmpdir)
            assert result == "python -m pytest -v --tb=short"

    def test_detect_empty_dir_returns_none(self):
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            result = tool._detect_test_framework(tmpdir)
            assert result is None

    def test_detect_binary_file_skipped(self):
        """Binary/unreadable files should not crash detection."""
        tool = TestRunnerTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            filepath = os.path.join(tmpdir, "pyproject.toml")
            with open(filepath, "wb") as f:
                f.write(b"\x00\x01\x02")
            result = tool._detect_test_framework(tmpdir)
            assert result is None


# ── TestRunnerTool._parse_test_result ──────────────────────────────────


class TestParseTestResult:
    """Tests for TestRunnerTool._parse_test_result string parsing."""

    def test_parse_pytest_all_passed(self):
        tool = TestRunnerTool()
        output = "collected 10 items\n\nmodule.py ......X..\n\n===== 10 passed in 0.12s ====="
        result = tool._parse_test_result(output, 0)
        assert result["passed"] is True
        assert result["returncode"] == 0
        assert result["passed_count"] == 10
        assert result["failed_count"] == 0
        assert result["error_count"] == 0
        assert result["total"] == 10

    def test_parse_pytest_with_failures(self):
        tool = TestRunnerTool()
        output = "collected 10 items\n\n===== 8 passed, 2 failed in 0.15s ====="
        result = tool._parse_test_result(output, 1)
        assert result["passed"] is False
        assert result["passed_count"] == 8
        assert result["failed_count"] == 2
        assert result["error_count"] == 0
        assert result["total"] == 10

    def test_parse_pytest_with_errors(self):
        tool = TestRunnerTool()
        output = "collected 5 items\n\n===== 3 passed, 1 failed, 1 error in 0.10s ====="
        result = tool._parse_test_result(output, 1)
        assert result["passed"] is False
        assert result["passed_count"] == 3
        assert result["failed_count"] == 1
        assert result["error_count"] == 1
        assert result["total"] == 5

    def test_parse_jest_output(self):
        tool = TestRunnerTool()
        output = "Tests:       10 passed, 10 total\nRan all test suites."
        result = tool._parse_test_result(output, 0)
        assert result["passed"] is True
        assert result["passed_count"] == 10
        assert result["total"] == 10

    def test_parse_jest_with_failures(self):
        tool = TestRunnerTool()
        output = "Tests:       8 passed, 2 failed, 10 total"
        result = tool._parse_test_result(output, 1)
        assert result["passed"] is False
        assert result["passed_count"] == 8
        assert result["failed_count"] == 2
        assert result["total"] == 10

    def test_parse_empty_output(self):
        tool = TestRunnerTool()
        result = tool._parse_test_result("", 0)
        assert result["passed"] is True
        assert result["total"] == 0
        assert result["errors"] == []

    def test_parse_error_extraction(self):
        tool = TestRunnerTool()
        output = (
            "collected 2 items\n\n"
            "===== 1 passed, 1 failed in 0.10s =====\n"
            "FAILED test_foo.py::test_bar - AssertionError: expected 5 got 3\n"
            "Error: test crash\n"
            "Traceback (most recent call last):\n"
            '  File "test.py", line 10, in test_bar'
        )
        result = tool._parse_test_result(output, 1)
        assert result["passed"] is False
        assert len(result["errors"]) > 0
        error_text = " ".join(result["errors"]).lower()
        assert "assertionerror" in error_text or "assertion" in error_text

    def test_parse_no_error_lines_when_passed(self):
        tool = TestRunnerTool()
        output = "===== 5 passed in 0.05s ====="
        result = tool._parse_test_result(output, 0)
        assert result["passed"] is True
        assert result["errors"] == []

    def test_parse_summary_format_correct(self):
        tool = TestRunnerTool()
        output = "===== 3 passed, 1 failed in 0.10s ====="
        result = tool._parse_test_result(output, 1)
        summary = result["summary"]
        assert "FAILED" in summary or "❌" in summary
        assert "Total: 4" in summary
        assert "Passed: 3" in summary
        assert "Failed: 1" in summary


# ── AutoLintTool._detect_linters ───────────────────────────────────────


class TestDetectLinters:
    """Tests for AutoLintTool._detect_linters file-based detection."""

    def test_detect_ruff_from_pyproject(self):
        tool = AutoLintTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pyproject.toml"), "w") as f:
                f.write('[tool.ruff]\ntarget-version = "py311"')
            linters = tool._detect_linters(tmpdir)
            assert any(lint["name"] == "ruff" for lint in linters)
            ruff = [lint for lint in linters if lint["name"] == "ruff"][0]
            assert ruff["cmd"] == "ruff check"
            assert ruff["fix_cmd"] == "ruff check --fix"

    def test_detect_eslint(self):
        tool = AutoLintTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, ".eslintrc.json"), "w") as f:
                f.write("{}")
            linters = tool._detect_linters(tmpdir)
            assert any(lint["name"] == "eslint" for lint in linters)

    def test_detect_eslint_js(self):
        tool = AutoLintTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, ".eslintrc.js"), "w") as f:
                f.write("module.exports = {};")
            linters = tool._detect_linters(tmpdir)
            assert any(lint["name"] == "eslint" for lint in linters)

    def test_detect_prettier(self):
        tool = AutoLintTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, ".prettierrc"), "w") as f:
                f.write("{}")
            linters = tool._detect_linters(tmpdir)
            assert any(lint["name"] == "prettier" for lint in linters)

    def test_detect_rustfmt(self):
        tool = AutoLintTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "Cargo.toml"), "w") as f:
                f.write("[package]")
            linters = tool._detect_linters(tmpdir)
            assert any(lint["name"] == "rustfmt" for lint in linters)

    def test_detect_gofmt(self):
        tool = AutoLintTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "go.mod"), "w") as f:
                f.write("module test")
            linters = tool._detect_linters(tmpdir)
            assert any(lint["name"] == "gofmt" for lint in linters)

    def test_detect_flake8(self):
        tool = AutoLintTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, ".flake8"), "w") as f:
                f.write("[flake8]")
            linters = tool._detect_linters(tmpdir)
            assert any(lint["name"] == "flake8" for lint in linters)

    def test_detect_no_linters(self):
        tool = AutoLintTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            linters = tool._detect_linters(tmpdir)
            assert linters == []

    def test_detect_multiple_linters(self):
        tool = AutoLintTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pyproject.toml"), "w") as f:
                f.write("[tool.ruff]")
            with open(os.path.join(tmpdir, ".eslintrc.json"), "w") as f:
                f.write("{}")
            with open(os.path.join(tmpdir, "Cargo.toml"), "w") as f:
                f.write("[package]")
            linters = tool._detect_linters(tmpdir)
            names = [lint["name"] for lint in linters]
            assert "ruff" in names
            assert "eslint" in names
            assert "rustfmt" in names

    def test_detect_black_fallback(self):
        tool = AutoLintTool()
        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, "pyproject.toml"), "w") as f:
                f.write("[tool.black]\nline-length = 88")
            linters = tool._detect_linters(tmpdir)
            assert any(lint["name"] == "black" for lint in linters)
            assert not any(lint["name"] == "ruff" for lint in linters)


# ── TestRunnerTool initialisation ──────────────────────────────────────


class TestTestRunnerToolInit:
    def test_name_and_description(self):
        tool = TestRunnerTool()
        assert tool.name == "run_tests"
        assert "test" in tool.description.lower()

    def test_schema_contains_required_fields(self):
        tool = TestRunnerTool()
        schema = tool.parameters_schema
        assert "command" in schema["properties"]
        assert "path" in schema["properties"]
        assert "timeout_seconds" in schema["properties"]
        assert "file_filter" in schema["properties"]


# ── AutoLintTool initialisation ────────────────────────────────────────


class TestAutoLintToolInit:
    def test_name_and_description(self):
        tool = AutoLintTool()
        assert tool.name == "auto_lint"
        assert "lint" in tool.description.lower()

    def test_schema_contains_properties(self):
        tool = AutoLintTool()
        schema = tool.parameters_schema
        assert "file_path" in schema["properties"]
        assert "fix" in schema["properties"]
        assert "path" in schema["properties"]


# ── PRCreationTool execution (mocked _git) ─────────────────────────────


class TestPRCreationTool:
    """Tests for PRCreationTool with mocked subprocess calls."""

    def test_name_and_description(self):
        tool = PRCreationTool()
        assert tool.name == "create_pr"
        assert "pull request" in tool.description.lower()

    def test_schema_contains_fields(self):
        tool = PRCreationTool()
        schema = tool.parameters_schema
        assert "title" in schema["properties"]
        assert "body" in schema["properties"]
        assert "base" in schema["properties"]
        assert "draft" in schema["properties"]
        assert "path" in schema["properties"]

    @patch("antigravity_k.tools.ci_tools.subprocess.run")
    def test_execute_auto_title_generation(self, mock_run):
        """When no title provided, should auto-generate from last commit."""
        mock_run.side_effect = [
            MagicMock(stdout="feature-branch\n", returncode=0),
            MagicMock(stdout="Fix login bug\n", returncode=0),
            MagicMock(stdout=" CHANGES:\nfile.py | 2 +-\n", returncode=0),
            MagicMock(stdout="- Fix login bug\n", returncode=0),
            MagicMock(stdout="https://github.com/example/repo/pull/1\n", returncode=0),
        ]
        tool = PRCreationTool()
        result = tool.execute()
        assert "PR created" in result or "created" in result
        # Verify gh command was called
        gh_calls = [c for c in mock_run.call_args_list if "gh" in str(c)]
        assert len(gh_calls) > 0

    @patch("antigravity_k.tools.ci_tools.subprocess.run")
    def test_execute_with_title(self, mock_run):
        """When title is provided, should use it directly."""
        mock_run.side_effect = [
            MagicMock(stdout="https://github.com/example/repo/pull/1\n", returncode=0),
        ]
        tool = PRCreationTool()
        result = tool.execute(title="My PR Title", body="Test body")
        assert "PR created" in result or "created" in result

    @patch("antigravity_k.tools.ci_tools.subprocess.run")
    def test_execute_draft_pr(self, mock_run):
        """Draft flag should be passed to gh command."""
        mock_run.side_effect = [
            MagicMock(stdout="https://github.com/example/repo/pull/1\n", returncode=0),
        ]
        tool = PRCreationTool()
        result = tool.execute(draft=True, title="Draft PR", body="Draft body")
        assert "PR created" in result or "created" in result
        # Verify --draft was passed to the gh command
        gh_call = mock_run.call_args_list[0]
        gh_args = gh_call[0][0]
        assert "--draft" in gh_args

    @patch("antigravity_k.tools.ci_tools.subprocess.run")
    def test_execute_gh_not_found(self, mock_run):
        """FileNotFoundError should give helpful message."""
        mock_run.side_effect = FileNotFoundError()
        tool = PRCreationTool()
        result = tool.execute(title="Test", body="Test body")
        assert "gh" in result.lower()

    @patch("antigravity_k.tools.ci_tools.subprocess.run")
    def test_execute_gh_error(self, mock_run):
        """Non-zero return from gh should be reported."""
        mock_run.side_effect = [
            MagicMock(stdout="", returncode=1, stderr="Error: no commits"),
        ]
        tool = PRCreationTool()
        result = tool.execute(title="Test", body="Body")
        assert "failed" in result.lower() or "error" in result.lower()
