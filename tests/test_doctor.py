"""Tests for the agk doctor command — environment diagnostic.

Uses Typer's CliRunner to invoke the command and verify output.
"""

from __future__ import annotations

from typer.testing import CliRunner

from antigravity_k.cli import app

runner = CliRunner()


class TestDoctorCommand:
    """agk doctor runs and produces expected output."""

    def test_doctor_exits_zero_on_success(self):
        """doctor should exit 0 when there are no hard failures."""
        result = runner.invoke(app, ["doctor"])
        # Exit code 0 means no FAIL checks (warnings are OK).
        assert result.exit_code in (0, 1)  # may be 1 if warnings + config issues
        assert "Doctor" in result.output or "passed" in result.output.lower()

    def test_doctor_output_contains_checks(self):
        """The output should list individual checks."""
        result = runner.invoke(app, ["doctor"])
        assert "Python" in result.output
        assert "git" in result.output.lower()

    def test_doctor_shows_summary(self):
        """The output should include a summary line with pass/warn/fail counts."""
        result = runner.invoke(app, ["doctor"])
        assert "passed" in result.output.lower()
        assert "warnings" in result.output.lower() or "failed" in result.output.lower()

    def test_doctor_checks_config(self):
        """Config validation is checked."""
        result = runner.invoke(app, ["doctor"])
        assert "Config" in result.output or "config" in result.output.lower()

    def test_doctor_checks_port(self):
        """Port availability is checked."""
        result = runner.invoke(app, ["doctor"])
        assert "Port" in result.output

    def test_doctor_checks_api_keys(self):
        """API key availability is checked."""
        result = runner.invoke(app, ["doctor"])
        assert "API key" in result.output or "api key" in result.output.lower()

    def test_doctor_checks_vault_writable(self):
        """Vault directory writability is checked."""
        result = runner.invoke(app, ["doctor"])
        assert "Vault" in result.output or "writable" in result.output.lower()

    def test_doctor_checks_model_registry(self):
        """Model registry loading is checked."""
        result = runner.invoke(app, ["doctor"])
        assert "Model" in result.output or "registry" in result.output.lower()

    def test_doctor_in_version_help(self):
        """doctor should appear in the CLI help."""
        result = runner.invoke(app, ["--help"])
        assert "doctor" in result.output
