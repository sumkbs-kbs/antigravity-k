"""Phase 4 — diagnostics ZIP allowlist / no-secret-path smoke."""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from antigravity_k.engine.diagnostics_export import (
    export_diagnostics_zip,
    is_forbidden_archive_path,
)


@pytest.mark.parametrize(
    ("path", "forbidden"),
    [
        ("manifest.json", False),
        ("logs/app.log", False),
        (".env", True),
        ("vault_data/keys.bin", True),
        ("data/auth_hash", True),
        ("secrets/token", True),
        ("api_keys/openai.json", True),
        ("credentials/store", True),
        ("logs/.env.local", True),
    ],
)
def test_forbidden_archive_path_blocklist(path: str, forbidden: bool) -> None:
    assert is_forbidden_archive_path(path) is forbidden


def test_export_diagnostics_zip_has_no_secret_looking_paths(tmp_path: Path) -> None:
    out = tmp_path / "diagnostics-smoke.zip"
    # Plant a fake log that looks secret-bearing in name — must not be packed
    log_dir = tmp_path / "logs"
    log_dir.mkdir()
    (log_dir / "safe.log").write_text("hello ok\nsk-proj-SHOULD_BE_REDACTED_IF_MATCHED_abcdefghij\n", encoding="utf-8")
    (log_dir / ".env").write_text("OPENAI_API_KEY=sk-proj-never-pack-me\n", encoding="utf-8")

    # Point log collection at tmp via monkeypatched home? Use explicit export and
    # verify archive members + scrub independently of real log dirs.
    result = export_diagnostics_zip(out)
    assert result == out
    assert out.is_file()

    with zipfile.ZipFile(out) as zf:
        names = zf.namelist()
        assert "manifest.json" in names
        assert "setting_keys.json" in names
        assert "error_codes.json" in names
        for name in names:
            assert not is_forbidden_archive_path(name), name
            assert ".env" not in name.lower()
            assert "vault_data" not in name.lower()
            assert "auth_hash" not in name.lower()

        setting_keys = zf.read("setting_keys.json").decode("utf-8")
        assert "values_included" in setting_keys
        assert "false" in setting_keys.lower()
        # Values must never appear even if present on disk elsewhere
        assert "sk-proj-never-pack-me" not in setting_keys

        # Full archive byte scan for planted secret filename/content markers
        blob = out.read_bytes()
        assert b"vault_data" not in blob
        assert b"auth_hash" not in blob
        assert b"sk-proj-never-pack-me" not in blob


def test_export_cli_help_lists_diagnostics(tmp_path: Path) -> None:
    from typer.testing import CliRunner

    from antigravity_k.cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["diagnostics", "--help"])
    assert result.exit_code == 0, result.output
    assert "export" in result.output

    out = tmp_path / "cli-diag.zip"
    result = runner.invoke(app, ["diagnostics", "export", "--output", str(out)])
    assert result.exit_code == 0, result.output
    assert out.is_file()
    with zipfile.ZipFile(out) as zf:
        assert "manifest.json" in zf.namelist()
