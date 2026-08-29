"""build_sandbox_argv와 persistent terminal의 샌드박스 라우팅 테스트."""

from antigravity_k.config import config as app_config
from antigravity_k.tools.terminal_tools import (
    PersistentTerminalManager,
    build_sandbox_argv,
)


def test_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(app_config.security, "sandbox_enabled", False)
    assert build_sandbox_argv("echo hi") is None


def test_returns_wrapped_argv_when_enabled_on_darwin(monkeypatch):
    import platform

    if platform.system() != "Darwin":
        monkeypatch.setattr("shutil.which", lambda name: "/usr/bin/sandbox-exec" if name == "sandbox-exec" else None)
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


def _assert_wrapped(monkeypatch):
    monkeypatch.setattr(app_config.security, "sandbox_enabled", True)
    result = build_sandbox_argv("echo hi")
    assert result is not None
    return result


def test_persistent_terminal_uses_sandbox_when_enabled(monkeypatch, tmp_path):
    import platform as _platform

    if _platform.system() != "Darwin":
        return  # sandbox-exec 없는 플랫폼에서는 raw 경로 유지가 계약

    monkeypatch.setattr(app_config.security, "sandbox_enabled", True)
    manager = PersistentTerminalManager()
    term_id = manager.create_terminal("echo sandbox-check", str(tmp_path))
    process = manager.terminals[term_id]
    assert process.args[0] == "sandbox-exec"
    # 종료 후 프로파일 정리 확인
    process.wait(timeout=15)
    manager.get_output(term_id)
    assert term_id not in manager.terminals


def test_persistent_terminal_raw_path_when_disabled(monkeypatch, tmp_path):
    monkeypatch.setattr(app_config.security, "sandbox_enabled", False)
    manager = PersistentTerminalManager()
    term_id = manager.create_terminal("echo raw-check", str(tmp_path))
    process = manager.terminals[term_id]
    assert isinstance(process.args, str) or process.args[-1] != "-c"
    process.wait(timeout=15)
    manager.get_output(term_id)
