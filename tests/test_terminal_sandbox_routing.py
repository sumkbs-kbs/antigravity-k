"""build_sandbox_argv와 persistent terminal의 샌드박스 라우팅 테스트."""

from pathlib import Path

import pytest

from antigravity_k.config import config as app_config
from antigravity_k.tools.terminal_tools import (
    PersistentTerminalManager,
    build_sandbox_argv,
)


def test_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(app_config.security, "sandbox_enabled", False)
    assert build_sandbox_argv("echo hi") is None


def test_returns_wrapped_argv_when_enabled_on_darwin(monkeypatch: pytest.MonkeyPatch) -> None:
    import platform

    if platform.system() != "Darwin":
        def which_stub(name: str) -> str | None:
            return "/usr/bin/sandbox-exec" if name == "sandbox-exec" else None

        monkeypatch.setattr(
            "shutil.which",
            which_stub,
        )
        orig = platform.system
        monkeypatch.setattr(platform, "system", lambda: "Darwin")
        try:
            result = _assert_wrapped(monkeypatch)
        finally:
            monkeypatch.setattr(platform, "system", orig)
    else:
        result = _assert_wrapped(monkeypatch)

    argv, profile_path = result
    assert argv[0] == "sandbox-exec"
    assert "-f" in argv and str(profile_path) in argv
    assert "/bin/sh" in argv and "-c" in argv
    assert profile_path.exists()
    profile_path.unlink()


def _assert_wrapped(monkeypatch: pytest.MonkeyPatch) -> tuple[list[str], Path]:
    monkeypatch.setattr(app_config.security, "sandbox_enabled", True)
    result = build_sandbox_argv("echo hi")
    assert result is not None
    return result


def test_persistent_terminal_uses_sandbox_when_enabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import platform as _platform

    if _platform.system() != "Darwin":
        return  # sandbox-exec 없는 플랫폼에서는 raw 경로 유지가 계약

    monkeypatch.setattr(app_config.security, "sandbox_enabled", True)
    manager = PersistentTerminalManager()
    term_id = manager.create_terminal("echo sandbox-check", str(tmp_path))
    process = manager.terminals[term_id]
    assert isinstance(process.args, list)
    assert process.args[0] == "sandbox-exec"
    # 종료 후 프로파일 정리 확인
    _ = process.wait(timeout=15)
    _ = manager.get_output(term_id)
    assert term_id not in manager.terminals


def test_persistent_terminal_raw_path_when_disabled(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(app_config.security, "sandbox_enabled", False)
    manager = PersistentTerminalManager()
    term_id = manager.create_terminal("echo raw-check", str(tmp_path))
    process = manager.terminals[term_id]
    assert isinstance(process.args, str) or (isinstance(process.args, list) and process.args[-1] != "-c")
    _ = process.wait(timeout=15)
    _ = manager.get_output(term_id)
