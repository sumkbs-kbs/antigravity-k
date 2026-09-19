"""task 13 계약 시험 — `web_search` 라우팅(opt-in 번들 provider).

여기서 고정하는 문장:

- **꺼져 있으면 아무 일도 없다**: `search.ssak.enabled=false` 면 기존 4-engine 경로가 그대로 돌고,
  번들 provider 는 **호출되지 않는다**(호출되면 시험이 깨진다).
- **켜면 한 번 간다**: 성공하면 bundle 결과로 끝나고 legacy engine 은 **한 번도 돌지 않는다**
  (fixture child 가 받은 호출 수로 센다 — "이중 fanout 없음").
- **대체는 transient 에만, 정확히 1회**: 시간 초과·전송 소실·child 종료·회로 열림은 legacy 로 1회,
  POLICY_DENIED(사용자가 이 요청에서 껐다)·INVALID_ARGUMENT·AUTH_REQUIRED·설정 오류는 **대체하지 않는다**.
- **경로는 신뢰된 루트만**: `artifact_path` 가 밖이면 spawn 0, legacy 대체도 없다.
- **동기 래퍼는 이벤트 루프를 중첩 실행하지 않는다**: 이미 돌고 있는 루프 안에서 `execute` 가 그대로 답한다.
- **설정 마이그레이션**: 기존 config.yaml 에 이 섹션이 없어도 default 로 채워지고, 있는 값은 안 덮어쓴다.

시험은 **실제 child 프로세스**를 쓴다(번들 shim = fixture child 를 실행하는 실행 파일 + 매니페스트).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import stat
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any, cast

import pytest

from antigravity_k.engine.tool_policy import ToolPolicy, reset_tool_policy, set_tool_policy
from antigravity_k.tools.mcp_tool_loader import MCPToolLoader
from antigravity_k.tools.mcp_tool_result import MCPToolOutcome, error_outcome
from antigravity_k.tools.ssak_search_provider import (
    ProviderAttempt,
    SsakSearchSettings,
    classify_error_code,
    is_trusted_artifact_path,
    resolve_manifest_path,
    search_with_bundled_provider,
    settings_snapshot,
)
from antigravity_k.tools.ssak_search_runtime import (
    SearchRuntimeConfig,
    SsakSearchRuntime,
    get_ssak_search_runtime,
    shutdown_ssak_search_runtime,
    verify_bundled_artifact,
)
from antigravity_k.tools.web_search_tool import WebSearchTool

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "ssak_search_child.py"
HERMETIC_ARGS: tuple[str, ...] = ("-I", "-S")


# ── 도우미 ────────────────────────────────────────────────────────────────────


def write_config(tmp_path: Path, ssak: dict[str, Any] | None = None, extra: str = "") -> Path:
    """`search.ssak.*` 를 가진 config.yaml 을 만들고 `AGK_CONFIG_FILE` 로 가리킨다(monkeypatch 필요)."""
    lines = ["search:", "  ssak:"]
    for key, value in (ssak or {}).items():
        lines.append(f"    {key}: {json.dumps(value) if isinstance(value, str) else value}")
    body = "\n".join(lines) + "\n" + extra
    path = tmp_path / "config.yaml"
    path.write_text(body, encoding="utf-8")
    return path


def bundle(tmp_path: Path, mode: str = "ok") -> tuple[Path, Path]:
    """실제로 실행되는 번들 shim + 매니페스트를 만든다(fixture child 를 띄운다).

    shim 은 `bin/ssak-mcp`, 매니페스트는 `release/ssak-search-manifest.json` — task 11 의 배치 규약
    그대로다. fixture child 가 호출 기록을 남기도록 `SSAK_CHILD_RECORD` 를 shim 안에서 세운다.
    """
    record = tmp_path / "calls.json"
    shim = tmp_path / "bin" / "ssak-mcp"
    shim.parent.mkdir(parents=True, exist_ok=True)
    shim.write_text(
        "#!/bin/sh\n"
        f'export SSAK_CHILD_RECORD="{record}"\n'
        f'exec "{sys.executable}" {" ".join(HERMETIC_ARGS)} "{FIXTURE}" {mode}\n',
        encoding="utf-8",
    )
    shim.chmod(shim.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    manifest = tmp_path / "release" / "ssak-search-manifest.json"
    manifest.parent.mkdir(parents=True, exist_ok=True)
    manifest.write_text(
        json.dumps(
            {
                "artifact": {
                    "sha256": hashlib.sha256(shim.read_bytes()).hexdigest(),
                    "platform": "darwin",
                    "arch": "arm64",
                }
            }
        ),
        encoding="utf-8",
    )
    return shim, manifest


def recorded_calls(record: Path) -> list[dict[str, object]]:
    path = Path(f"{record}.calls")
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def enable(monkeypatch: pytest.MonkeyPatch, tmp_path: Path, shim: Path, **overrides: object) -> None:
    """번들 provider 를 켠 상태로 만든다(신뢰 루트 = tmp_path)."""
    ssak: dict[str, Any] = {
        "enabled": True,
        "artifact_path": str(shim),
        **overrides,
    }
    config = write_config(tmp_path, ssak)
    monkeypatch.setenv("AGK_CONFIG_FILE", str(config))
    monkeypatch.setenv("AGK_SEARCH_TRUSTED_ROOTS", str(tmp_path))
    monkeypatch.delenv("AGK_SEARCH_SSAK_ENABLED", raising=False)
    monkeypatch.delenv("AGK_SEARCH_SSAK_ARTIFACT_PATH", raising=False)


@pytest.fixture
def bundled_host(tmp_path: Path) -> Iterator[None]:
    """실제 child 를 쓰는 시험 뒤에 호스트 싱글턴을 반드시 닫는다(child 0)."""
    yield
    status = shutdown_ssak_search_runtime(timeout=20)
    if status is not None:
        assert status["child_pids"] == [], f"child 가 남았다: {status}"


def install_legacy(monkeypatch: pytest.MonkeyPatch, tool: WebSearchTool) -> dict[str, int]:
    """legacy 4-engine 을 고정 결과로 바꾸고 호출 횟수를 센다(네트워크 없이)."""
    calls = {"engines": 0, "provider": 0}

    def fixed(query: str, *args: object, **kwargs: object) -> list[tuple[str, str, str]]:
        calls["engines"] += 1
        return [("legacy title", "https://legacy.example/x", "legacy snippet")]

    monkeypatch.setattr(tool, "_sync_search_self_hosted", fixed)
    monkeypatch.setattr(tool, "_sync_search_searxng", fixed)
    monkeypatch.setattr(tool, "_sync_search_jina", fixed)
    monkeypatch.setattr(tool, "_sync_search_duckduckgo", fixed)
    monkeypatch.setattr(tool.engine, "_extract_content_jina", lambda *a, **k: "")
    return calls


def install_provider(monkeypatch: pytest.MonkeyPatch, attempt: ProviderAttempt | None, calls: dict[str, int]) -> None:
    """번들 provider 호출을 시험용 attempt 로 바꾼다(호출 횟수를 센다)."""

    def fake(query: str, **kwargs: object) -> ProviderAttempt:
        calls["provider"] += 1
        assert attempt is not None
        return attempt

    monkeypatch.setattr("antigravity_k.tools.web_search_tool.search_with_bundled_provider", fake)


# ── A. 라우팅 결정 ────────────────────────────────────────────────────────────


def test_flag_off_runs_the_legacy_engines_and_never_touches_the_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    tool = WebSearchTool()
    calls = install_legacy(monkeypatch, tool)

    def explode(*args: object, **kwargs: object) -> ProviderAttempt:
        raise AssertionError("꺼져 있는데 번들 provider 를 호출했다")

    monkeypatch.setattr("antigravity_k.tools.web_search_tool.search_with_bundled_provider", explode)
    output = tool.execute(query="opt-in 없는 검색")

    assert "legacy title" in output
    assert calls["engines"] > 0
    assert tool._last_route.startswith("legacy")
    assert settings_snapshot().enabled is False


def test_opt_in_answers_from_the_bundle_without_running_legacy(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bundled_host: None
) -> None:
    shim, _manifest = bundle(tmp_path)
    enable(monkeypatch, tmp_path, shim)
    tool = WebSearchTool()
    calls = install_legacy(monkeypatch, tool)

    output = tool.execute(query="번들 검색")

    assert tool._last_route.startswith("bundled"), tool._last_route
    assert calls["engines"] == 0, "번들 성공인데 legacy engine 이 돌았다"
    assert "[웹 검색 결과]" in output
    assert "SsakBundle" in output
    # 실제 child 가 **한 번** 호출됐다(이중 fanout 없음).
    assert [call["name"] for call in recorded_calls(tmp_path / "calls.json")] == ["ssak_search"]


def test_transient_failure_falls_back_to_legacy_exactly_once(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim, _manifest = bundle(tmp_path)
    enable(monkeypatch, tmp_path, shim)
    tool = WebSearchTool()
    calls = install_legacy(monkeypatch, tool)
    install_provider(monkeypatch, ProviderAttempt(False, True, "child exited", error_code="CHILD_EXITED"), calls)

    output = tool.execute(query="일시 장애")

    assert calls["provider"] == 1, "provider 호출이 1회가 아니다"
    assert calls["engines"] > 0, "transient 실패인데 legacy 대체가 없었다"
    assert "legacy title" in output
    assert tool._last_route == "bundled→legacy (transient CHILD_EXITED)"


@pytest.mark.parametrize(
    ("code", "message"),
    [
        ("POLICY_DENIED", "blocked by request policy"),
        ("INVALID_ARGUMENT", "query is required"),
        ("AUTH_REQUIRED", "401 from upstream"),
        ("UNTRUSTED_ARTIFACT_PATH", "artifact outside trusted roots"),
        ("SOMETHING_NEW", "unknown failure nobody classified"),
    ],
)
def test_permanent_failures_are_reported_without_fallback(
    code: str, message: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    shim, _manifest = bundle(tmp_path)
    enable(monkeypatch, tmp_path, shim)
    tool = WebSearchTool()
    calls = install_legacy(monkeypatch, tool)
    transient = classify_error_code(code) == "transient"
    install_provider(monkeypatch, ProviderAttempt(False, transient, message, error_code=code), calls)

    output = tool.execute(query="결정적 실패")

    assert calls["provider"] == 1
    assert calls["engines"] == 0, f"{code} 인데 legacy 로 대체됐다"
    assert output.startswith("Search Error:")
    assert f"({code})" in tool._last_route


def test_invalid_config_is_reported_instead_of_silently_using_legacy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    # enabled=true 인데 artifact_path 가 없다 — fail-closed. 조용히 legacy 로 도는 것이 금지다.
    config = write_config(tmp_path, {"enabled": True})
    monkeypatch.setenv("AGK_CONFIG_FILE", str(config))
    tool = WebSearchTool()
    calls = install_legacy(monkeypatch, tool)

    output = tool.execute(query="설정 오류")

    assert output.startswith("Search Error:") and "artifact_path" in output
    assert calls["engines"] == 0
    assert tool._last_route.startswith("blocked")


def test_fallback_policy_none_never_uses_legacy(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim, _manifest = bundle(tmp_path)
    enable(monkeypatch, tmp_path, shim, fallback="none")
    tool = WebSearchTool()
    calls = install_legacy(monkeypatch, tool)
    install_provider(monkeypatch, ProviderAttempt(False, True, "timeout", error_code="TIMEOUT"), calls)

    output = tool.execute(query="대체 금지 정책")

    assert output.startswith("Search Error:")
    assert calls["engines"] == 0


def test_sync_wrapper_does_not_nest_a_run_inside_a_running_loop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bundled_host: None
) -> None:
    """이미 돌고 있는 루프 안에서 `execute` 가 그대로 답한다(중첩 run 이면 RuntimeError 로 죽는다)."""

    shim, _manifest = bundle(tmp_path)
    enable(monkeypatch, tmp_path, shim)
    tool = WebSearchTool()

    async def inside_a_loop() -> str:
        return tool.execute(query="루프 안 검색")

    output = asyncio.run(inside_a_loop())

    assert "[웹 검색 결과]" in output
    assert tool._last_route.startswith("bundled")


# ── B. provider ↔ 런타임 ──────────────────────────────────────────────────────


def test_untrusted_artifact_path_is_refused_before_spawn(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    shim, _manifest = bundle(tmp_path)
    settings = SsakSearchSettings(enabled=True, artifact_path=str(shim), extra_trusted_roots=())
    monkeypatch.delenv("AGK_SEARCH_TRUSTED_ROOTS", raising=False)

    assert is_trusted_artifact_path(str(shim), ()) is False
    attempt = search_with_bundled_provider("질의", settings=settings)

    assert attempt.ok is False
    assert attempt.transient is False
    assert attempt.error_code == "UNTRUSTED_ARTIFACT_PATH"
    assert "trusted" in attempt.message


def test_trusted_root_env_makes_the_bundle_reachable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bundled_host: None
) -> None:
    shim, manifest = bundle(tmp_path)
    monkeypatch.setenv("AGK_SEARCH_TRUSTED_ROOTS", str(tmp_path))
    settings = SsakSearchSettings(
        enabled=True,
        artifact_path=str(shim),
        manifest_path=str(manifest),
        extra_trusted_roots=(str(tmp_path),),
    )

    attempt = search_with_bundled_provider("번들 질의", settings=settings)

    assert attempt.ok is True, attempt.message
    assert attempt.results, "hit 이 비었다"
    assert attempt.results[0][0] == "a"  # fixture 가 돌려주는 고정 hit
    assert attempt.transient is False


def test_manifest_is_discovered_beside_the_bundle(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim, manifest = bundle(tmp_path)

    assert resolve_manifest_path(shim, None) == manifest.resolve()
    assert resolve_manifest_path(shim, str(manifest)) == manifest
    # 없는 규약이면 None — 런타임이 fail-closed 로 거절한다(여기서 추측하지 않는다).
    lonely = tmp_path / "lonely-root" / "only" / "artifact"
    lonely.parent.mkdir(parents=True)
    lonely.write_text("x", encoding="utf-8")
    assert resolve_manifest_path(lonely, None) is None
    # 빈 환경변수는 "설정하지 않음"이다 — `Path("")` 는 `.` 이라 매니페스트로 읽히면 디렉터리를 연다.
    monkeypatch.setenv("AGK_SEARCH_MANIFEST", "")
    assert resolve_manifest_path(lonely, None) is None


class _StubOutcome:
    """`MCPToolOutcome` 의 최소 표면(파싱 시험용)."""

    def __init__(self, payload: object, *, text: str | None = None) -> None:
        self.structured_content = payload
        self.is_error = False
        self.error_code: str | None = None
        self._text = text if text is not None else json.dumps(payload, ensure_ascii=False)

    def __str__(self) -> str:
        return self._text


def test_empty_manifest_string_is_not_treated_as_a_path(tmp_path: Path) -> None:
    """`manifest_path=""` 를 경로로 읽으면 `Path("")` = `.` 이라 매니페스트 자리에 디렉터리가 온다.

    실제로 이 실수(task 13 구현 중)가 child 시작을 막고 **transient 로 오분류**돼 legacy 로 샜다 —
    빈 문자열은 "주지 않음"이고, 그 경우는 fail-closed 로 거절돼야 한다.
    """
    shim, _manifest = bundle(tmp_path)

    verdict = verify_bundled_artifact(shim, "")

    assert verdict.ok is False
    assert "no manifest given" in verdict.detail


def test_hits_are_read_from_structured_content_or_from_the_text_body(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    settings = SsakSearchSettings(enabled=True, artifact_path=str(tmp_path / "x"), extra_trusted_roots=(str(tmp_path),))
    payload = {"query": "q", "hits": [{"title": "T", "url": "https://e/x", "snippet": "S"}]}

    class _Runtime:
        def __init__(self, outcome: object) -> None:
            self._outcome = outcome

        def call_tool(self, name: str, arguments: object = None, **kwargs: object) -> object:
            return self._outcome

    structured = search_with_bundled_provider("q", settings=settings, runtime=_Runtime(_StubOutcome(payload)))
    assert structured.ok is True
    assert structured.results == [("T", "https://e/x", "S")]

    # structuredContent 가 없는 구현(legacy 어댑터)도 본문 JSON 으로 읽는다.
    text_only = _StubOutcome(None, text=f"prefix\n{json.dumps(payload)}")
    from_text = search_with_bundled_provider("q", settings=settings, runtime=_Runtime(text_only))
    assert from_text.results == [("T", "https://e/x", "S")]

    # hit 이 없으면 성공이지만 결과 0건이다(장애로 둔갑시키지 않는다).
    empty = search_with_bundled_provider("q", settings=settings, runtime=_Runtime(_StubOutcome({"hits": []})))
    assert empty.ok is True and empty.results == []


def test_request_policy_denial_is_permanent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    shim, manifest = bundle(tmp_path)
    monkeypatch.setenv("AGK_SEARCH_TRUSTED_ROOTS", str(tmp_path))
    settings = SsakSearchSettings(
        enabled=True,
        artifact_path=str(shim),
        manifest_path=str(manifest),
        extra_trusted_roots=(str(tmp_path),),
    )
    token = set_tool_policy(ToolPolicy(denied_tools=frozenset({"ssak_search"})))
    try:
        attempt = search_with_bundled_provider("질의", settings=settings)
    finally:
        reset_tool_policy(token)

    assert attempt.ok is False
    assert attempt.error_code == "POLICY_DENIED"
    assert attempt.transient is False, "사용자가 끈 요청을 transient 로 보면 legacy 로 새어 나간다"


def test_crash_loop_reports_circuit_open_as_transient(tmp_path: Path) -> None:
    _shim, _manifest = bundle(tmp_path, mode="crash_start")
    record = tmp_path / "crashed.json"
    runtime = SsakSearchRuntime(
        SearchRuntimeConfig(
            command=sys.executable,
            args=(*HERMETIC_ARGS, str(FIXTURE), "crash_start"),
            require_manifest=False,
            backoff_seconds=(0.05, 0.05, 0.15),
            ready_timeout_seconds=5.0,
            monitor_interval_seconds=0.05,
        )
    )
    settings = SsakSearchSettings(enabled=True, artifact_path=str(record), extra_trusted_roots=(str(tmp_path),))
    try:
        attempt = search_with_bundled_provider("질의", settings=settings, runtime=runtime)
    finally:
        status = runtime.shutdown(timeout=20)

    assert attempt.ok is False
    assert attempt.error_code == "CIRCUIT_OPEN", attempt.message
    assert attempt.transient is True, "반복된 transient 실패는 대체 허용이어야 한다"
    assert status["child_pids"] == []


def test_direct_ssak_search_and_web_search_share_one_child(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bundled_host: None
) -> None:
    shim, manifest = bundle(tmp_path)
    enable(monkeypatch, tmp_path, shim)
    tool = WebSearchTool()

    _ = tool.execute(query="먼저 web_search")

    runtime = get_ssak_search_runtime(
        SearchRuntimeConfig(artifact_path=str(shim), manifest_path=str(manifest), enabled=True)
    )
    loader = MCPToolLoader(config_path=None, include_system_tools=False, load_skill_servers=False)
    tools = loader.load_bundled_search_tools(runtime)
    assert sorted(entry.name for entry in tools) == ["count_calls", "mutating_write", "ssak_search"]
    direct = next(entry for entry in tools if entry.name == "ssak_search")
    outcome = cast("MCPToolOutcome", direct.execute(query="직접 호출"))
    assert outcome.is_error is False

    status = runtime.status()
    assert status["spawn_attempts"] == 1, f"child 가 두 번 만들어졌다: {status}"
    # 주의: `child_pids()` 는 cmdline 으로 child 를 찾으므로 여기서는 0 이다 — 이 시험의 번들 shim 은
    # `exec python … fixture.py` 라 프로세스 이름이 python 이다(실제 번들은 `bin/ssak-mcp` 로 잡힌다 —
    # task 12 의 pid tree 증거). 대신 **두 호출을 처리한 child 의 pid 가 같은지**로 한 child 를 증명한다.
    first_pid = json.loads((tmp_path / "calls.json").read_text(encoding="utf-8"))["pid"]
    names = [call["name"] for call in recorded_calls(tmp_path / "calls.json")]
    assert names == ["ssak_search", "ssak_search"], names
    second_pid = json.loads((tmp_path / "calls.json").read_text(encoding="utf-8"))["pid"]
    assert first_pid == second_pid, "두 번째 child 가 만들어졌다(같은 질의가 두 런타임에 흩어졌다)"


def test_typed_transport_errors_are_transient() -> None:
    """런타임이 돌려주는 코드 집합이 분류표와 어긋나지 않는지(문자열 추측 금지)."""
    for code in ("TIMEOUT", "TRANSPORT_LOST", "CHILD_EXITED", "RUNTIME_STOPPED", "RUNTIME_NOT_READY", "CIRCUIT_OPEN"):
        assert classify_error_code(code) == "transient", code
    for code in (
        "POLICY_DENIED",
        "INVALID_ARGUMENT",
        "AUTH_REQUIRED",
        "RUNTIME_DISABLED",
        "NON_IDEMPOTENT_NOT_RETRIED",
    ):
        assert classify_error_code(code) == "permanent", code
    assert classify_error_code(None) == "permanent"
    assert classify_error_code("SOMETHING_NEW") == "permanent"

    runtime_code = error_outcome("boom", error_code="CHILD_EXITED")
    assert classify_error_code(str(runtime_code.error_code)) == "transient"
    assert isinstance(runtime_code, MCPToolOutcome)


# ── C. 설정 ───────────────────────────────────────────────────────────────────


def test_config_defaults_are_added_without_overwriting_user_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # 사용자 설정에는 ssak 섹션이 없고, search 아래 다른 키가 있다 — 덮어쓰지 않고 default 만 더한다.
    config = tmp_path / "config.yaml"
    config.write_text(
        "search:\n  engine_url: https://user.example\nmodel:\n  api_engine: none\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("AGK_CONFIG_FILE", str(config))
    monkeypatch.delenv("AGK_SEARCH_SSAK_ENABLED", raising=False)

    settings = settings_snapshot()

    assert settings.enabled is False
    assert settings.mode == "bundled_stdio"
    assert settings.fallback == "legacy_on_transient"
    assert settings.artifact_path is None
    assert settings.problem is None
    from antigravity_k.config import AppConfig

    app = AppConfig()
    assert app.search.ssak.enabled is False
    assert app._raw["search"] == {"engine_url": "https://user.example"}  # 원문 보존


def test_env_overrides_win_over_yaml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, bundled_host: None) -> None:
    shim, _manifest = bundle(tmp_path)
    config = write_config(tmp_path, {"enabled": False})
    monkeypatch.setenv("AGK_CONFIG_FILE", str(config))
    monkeypatch.setenv("AGK_SEARCH_SSAK_ENABLED", "true")
    monkeypatch.setenv("AGK_SEARCH_SSAK_ARTIFACT_PATH", str(shim))
    monkeypatch.setenv("AGK_SEARCH_TRUSTED_ROOTS", str(tmp_path))

    settings = settings_snapshot()

    assert settings.enabled is True
    assert settings.artifact_path == str(shim)
    attempt = search_with_bundled_provider("환경변수 우선", settings=settings)
    assert attempt.ok is True, attempt.message


def test_engine_url_env_still_belongs_to_the_legacy_path(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """기존 `AGK_SEARCH_ENGINE_URL` 류 env 가 새 섹션 필드로 오해되지 않는지(회귀 방지)."""
    config = write_config(tmp_path, {"enabled": False})
    monkeypatch.setenv("AGK_CONFIG_FILE", str(config))
    monkeypatch.setenv("AGK_SEARCH_ENGINE_URL", "https://legacy.example")
    monkeypatch.delenv("AGK_SEARCH_SSAK_ENABLED", raising=False)

    settings = settings_snapshot()

    assert settings.enabled is False
    assert settings.artifact_path is None
    assert not hasattr(settings, "engine_url")


def test_windows_style_separator_in_trusted_roots_is_split_by_platform(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("AGK_SEARCH_TRUSTED_ROOTS", os.pathsep.join([str(tmp_path), "/nonexistent-root"]))
    settings = settings_snapshot()

    assert str(tmp_path) in settings.extra_trusted_roots
    assert is_trusted_artifact_path(tmp_path / "bundle", settings.extra_trusted_roots) is True
