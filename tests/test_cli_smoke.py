from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path
from typing import Final

from typer.testing import CliRunner

from antigravity_k.cli import app

PROJECT_ROOT: Final = Path(__file__).resolve().parents[1]


def _run_cli(*arguments: str, cwd: Path = PROJECT_ROOT) -> subprocess.CompletedProcess[str]:
    environment = os.environ.copy()
    environment["COLUMNS"] = "80"
    return subprocess.run(
        [sys.executable, "-m", "antigravity_k.cli", *arguments],
        check=False,
        cwd=cwd,
        capture_output=True,
        env=environment,
        text=True,
    )


def test_module_cli_help_exposes_documented_commands() -> None:
    result = _run_cli("--help")

    assert result.returncode == 0, result.stderr
    assert "serve" in result.stdout
    assert "models" in result.stdout
    assert "doctor" in result.stdout
    assert "task" in result.stdout


def test_module_cli_models_includes_default_local_qwen_profile() -> None:
    result = _run_cli("model", "list")

    assert result.returncode == 0, result.stderr
    assert "qwen3.6:latest" in result.stdout
    assert "Ollama" in result.stdout


def test_memory_alias_cli_creates_and_lists_project_schema(tmp_path: Path) -> None:
    # Given: an empty project workspace.
    project_root = tmp_path / "project"
    project_root.mkdir()

    # When: the operator creates and lists a project memory alias.
    created = _run_cli("memory", "alias-set", "database", "primary_db", cwd=project_root)
    listed = _run_cli("memory", "aliases", cwd=project_root)

    # Then: both commands succeed and the typed schema is persisted locally.
    assert created.returncode == 0, created.stderr
    assert listed.returncode == 0, listed.stderr
    assert "database" in listed.stdout
    assert "primary_db" in listed.stdout
    schema = (project_root / ".antigravity" / "memory" / "project_aliases.json").read_text(
        encoding="utf-8",
    )
    assert '"database"' in schema
    assert '"primary_db"' in schema


def test_memory_alias_cli_removes_alias_without_deleting_group_peers(tmp_path: Path) -> None:
    # Given: one canonical key has two aliases.
    project_root = tmp_path / "project"
    project_root.mkdir()
    _ = _run_cli("memory", "alias-set", "database", "primary_db", cwd=project_root)
    _ = _run_cli("memory", "alias-set", "database", "storage_backend", cwd=project_root)

    # When: one alias is removed.
    removed = _run_cli("memory", "alias-remove", "primary_db", cwd=project_root)
    listed = _run_cli("memory", "aliases", cwd=project_root)

    # Then: only the selected alias disappears.
    assert removed.returncode == 0, removed.stderr
    assert "primary_db" not in listed.stdout
    assert "storage_backend" in listed.stdout


def test_memory_alias_cli_rejects_builtin_redefinition_without_writing(tmp_path: Path) -> None:
    # Given: an empty project workspace.
    project_root = tmp_path / "project"
    project_root.mkdir()

    # When: the operator attempts to map a built-in key to a conflicting meaning.
    result = _run_cli("memory", "alias-set", "cache_backend", "database", cwd=project_root)

    # Then: validation fails and no schema is written.
    assert result.returncode != 0
    assert "alias" in (result.stdout + result.stderr).lower()
    assert not (project_root / ".antigravity" / "memory" / "project_aliases.json").exists()


def test_memory_alias_cli_rejects_unknown_removal_without_rewriting(tmp_path: Path) -> None:
    # Given: one valid alias schema already exists.
    project_root = tmp_path / "project"
    project_root.mkdir()
    created = _run_cli("memory", "alias-set", "database", "primary_db", cwd=project_root)
    path = project_root / ".antigravity" / "memory" / "project_aliases.json"
    original = path.read_bytes()

    # When: the operator removes an alias that is not configured.
    result = _run_cli("memory", "alias-remove", "missing_alias", cwd=project_root)

    # Then: the command fails and preserves the original schema bytes.
    assert created.returncode == 0, created.stderr
    assert result.returncode != 0
    assert path.read_bytes() == original


def test_task_resume_cli_waits_and_prints_accumulated_output(monkeypatch) -> None:
    from antigravity_k.api import dependencies

    class Runtime:
        def resume_task(self, task_id: str, target_model: str = "") -> bool:
            assert task_id == "direct_cli_001"
            assert target_model == "qwen3.6:latest"
            return True

        def wait_task(self, task_id: str, timeout: float | None = None) -> dict[str, object] | None:
            assert task_id == "direct_cli_001"
            assert timeout == 12
            return {"task_id": task_id, "status": "done"}

        def get_task_output(self, task_id: str) -> str | None:
            assert task_id == "direct_cli_001"
            return "partial-output\nDIRECT_RESUME_OK"

    monkeypatch.setattr(dependencies, "get_agent_runtime", lambda: Runtime())

    result = CliRunner().invoke(
        app,
        ["task", "resume", "direct_cli_001", "--model", "qwen3.6:latest", "--timeout", "12"],
    )

    assert result.exit_code == 0, result.output
    assert "DIRECT_RESUME_OK" in result.output
    assert "done" in result.output
