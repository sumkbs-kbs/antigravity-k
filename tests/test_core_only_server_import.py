from __future__ import annotations

import subprocess
import sys

_IMPORT_SERVER_WITHOUT_PLAYWRIGHT = """
import builtins

real_import = builtins.__import__

def import_without_playwright(name, *args, **kwargs):
    if name == "playwright" or name.startswith("playwright."):
        raise ModuleNotFoundError("No module named playwright")
    return real_import(name, *args, **kwargs)

builtins.__import__ = import_without_playwright
from antigravity_k.api.server import app
print(app.title)
"""


def test_server_import_does_not_require_dev_only_playwright() -> None:
    # Given: a core runtime where the dev-only Playwright package cannot be imported.
    # When: a fresh interpreter imports the production FastAPI server entrypoint.
    result = subprocess.run(
        [sys.executable, "-c", _IMPORT_SERVER_WITHOUT_PLAYWRIGHT],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    # Then: route registration completes without loading the optional browser backend.
    assert result.returncode == 0, result.stderr
    assert "Antigravity-K API" in result.stdout
