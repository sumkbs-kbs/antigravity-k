"""테스트: 세션 슬래시 커맨드 핸들러 (/help /tools /context /memory 등).
============================================================
각 핸들러의 미연결 가드, 렌더링 계약, 서브커맨드 분기를 검증한다.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Protocol, cast, final

import pytest

from antigravity_k.engine.slash_commands_session import SlashCommandSessionMixin

JsonObject = dict[str, object]


class SessionStub(Protocol):
    _current_session: JsonObject
    get_messages: Callable[[], list[JsonObject]]
    get_memory: Callable[[str], object | None]
    get_all_memory: Callable[[], JsonObject]
    get_session_info: Callable[[], JsonObject | None]
    list_sessions: Callable[[], list[JsonObject]]
    load_session: Callable[[str], bool]
    save: Callable[[], None]


def _session_messages() -> list[JsonObject]:
    return [{"role": "user", "content": "hi"}]


def _memory_value(key: str) -> object | None:
    return {"lang": "ko"}.get(key)


def _empty_memory() -> JsonObject:
    return {}


def _empty_session_info() -> JsonObject | None:
    return None


def _empty_sessions() -> list[JsonObject]:
    return []


def _failed_load(_sid: str) -> bool:
    return False


def _empty_usage(_messages: object) -> JsonObject:
    return {}


def _empty_stats() -> JsonObject:
    return {}


def _full_usage(_messages: object) -> JsonObject:
    return {
        "usage_pct": 50,
        "total_tokens": 1000,
        "max_tokens": 2000,
        "budget_remaining": 1000,
        "by_role": {"system": 800, "user": 200},
    }


def _full_stats() -> JsonObject:
    return {"total_shaped": 3, "tokens_saved": 500, "collapses": 1}


def _set_model(_name: str) -> None:
    return None


def _fail_set_model(_name: str) -> None:
    raise ValueError("없음")


def _shape_messages(messages: list[JsonObject]) -> list[JsonObject]:
    return messages[:1]


def _estimate_tokens(messages: list[JsonObject]) -> int:
    return len(messages) * 10


def _tool_count(_self: object) -> int:
    return 7


def _tool(
    name: str = "read_file",
    category: str = "file",
    risk: str = "safe",
    icon: str = "📄",
    desc: str = "파일 읽기",
) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        category=SimpleNamespace(value=category),
        risk_level=SimpleNamespace(value=risk),
        icon=icon,
        description=desc,
    )


def _command(
    name: str = "tools",
    category: str = "session",
    usage: str = "/tools",
    description: str = "도구 목록",
) -> SimpleNamespace:
    return SimpleNamespace(name=name, category=category, usage=usage, description=description)


@final
class _Host(SlashCommandSessionMixin):
    def __init__(
        self,
        *,
        commands: object | None = None,
        tools: object | None = None,
        session: object | None = None,
        shaper: object | None = None,
        model: object | None = None,
    ) -> None:
        setattr(self, "_commands", commands or {})
        setattr(self, "_tool_registry", tools)
        setattr(self, "_session_manager", session)
        setattr(self, "_context_shaper", shaper)
        setattr(self, "_model_manager", model)


def _invoke(host: _Host, command: str, args: list[str]) -> str:
    handler = cast(Callable[[list[str]], str], getattr(host, command))
    return handler(args)


@pytest.fixture
def session_stub() -> SessionStub:
    return cast(
        SessionStub,
        cast(
            object,
            SimpleNamespace(
                get_messages=_session_messages,
                get_memory=_memory_value,
                get_all_memory=_empty_memory,
                get_session_info=_empty_session_info,
                list_sessions=_empty_sessions,
                load_session=_failed_load,
                save=lambda: None,
                _current_session={"messages": []},
            ),
        ),
    )


# ─── /help · /tools ──────────────────────────────────────────────


class TestHelpAndTools:
    def test_help_groups_by_category_sorted(self) -> None:
        host = _Host(
            commands={
                "b": _command("beta", "agent", usage="/beta"),
                "a": _command("alpha", "agent", usage="/alpha"),
                "t": _command("tools", "session", usage="/tools"),
            }
        )

        out = _invoke(host, "_cmd_help", [])

        assert "### AGENT" in out and "### SESSION" in out
        assert out.index("`/alpha`") < out.index("`/beta`")
        assert "`/tools`" in out

    def test_tools_without_registry(self) -> None:
        assert _invoke(_Host(), "_cmd_tools", []) == "Tool registry not connected."

    def test_tools_lists_with_risk_icons_and_count(self) -> None:
        host = _Host(
            tools=SimpleNamespace(
                get_all=lambda: [
                    _tool("safe_tool", risk="safe"),
                    _tool(name="mystery", risk="weird"),
                ]
            )
        )

        out = _invoke(host, "_cmd_tools", [])

        assert "`safe_tool` 🟢" in out
        assert "`mystery` ⚪" in out
        assert "총 2개 도구 등록됨" in out

    def test_tools_category_filter(self) -> None:
        host = _Host(
            tools=SimpleNamespace(
                get_all=lambda: [
                    _tool("reader", category="file"),
                    _tool("searcher", category="search"),
                ]
            )
        )

        out = _invoke(host, "_cmd_tools", ["file"])

        assert "`reader`" in out
        assert "`searcher`" not in out


# ─── /context ────────────────────────────────────────────────────


class TestContextCommand:
    def test_missing_shaper_or_session(self) -> None:
        assert _invoke(_Host(shaper=None, session=object()), "_cmd_context", []) == ("Context shaper not connected.")
        shaper = SimpleNamespace(get_token_usage=_empty_usage, get_stats=_empty_stats)
        assert _invoke(_Host(shaper=shaper), "_cmd_context", []) == "Session manager not connected."

    def test_full_render_includes_bar_and_roles(self, session_stub: SessionStub) -> None:
        shaper = SimpleNamespace(
            get_token_usage=_full_usage,
            get_stats=_full_stats,
        )
        host = _Host(session=session_stub, shaper=shaper)

        out = _invoke(host, "_cmd_context", [])

        assert "█" * 10 in out and "░" * 10 in out
        assert "50%" in out
        assert "system: 800" in out
        assert "총 압축: 3회" in out


# ─── /memory · /model ────────────────────────────────────────────


class TestMemoryAndModel:
    def test_memory_key_lookup_hit_and_miss(self, session_stub: SessionStub) -> None:
        host = _Host(session=session_stub)

        assert _invoke(host, "_cmd_memory", ["lang"]) == "**lang:** ko"
        assert _invoke(host, "_cmd_memory", ["nope"]) == "Memory key 'nope' not found."

    def test_memory_empty_and_listing_truncates_long_values(self) -> None:
        @final
        class EmptySession:
            def get_all_memory(self) -> JsonObject:
                return {}

            def get_memory(self, _key: str) -> object | None:
                return None

        assert _invoke(_Host(session=EmptySession()), "_cmd_memory", []) == "Working Memory is empty."

        long_value = "x" * 250

        @final
        class Session:
            def get_all_memory(self) -> JsonObject:
                return {"big": long_value}

            def get_memory(self, _key: str) -> object | None:
                return None

        out = _invoke(_Host(session=Session()), "_cmd_memory", [])
        assert long_value not in out
        assert "x" * 100 in out

    def test_memory_without_session_manager(self) -> None:
        assert _invoke(_Host(), "_cmd_memory", []) == "Session manager not connected."

    def test_model_set_success_and_failure(self) -> None:
        manager = SimpleNamespace(set_model=_set_model)
        host = _Host(model=manager)

        assert "변경되었습니다" in _invoke(host, "_cmd_model", ["qwen3-test"])

        failing = SimpleNamespace(set_model=_fail_set_model)
        out = _invoke(_Host(model=failing), "_cmd_model", ["ghost"])
        assert "모델 변경 실패" in out

    def test_model_info_and_unavailable(self) -> None:
        host = _Host(model=SimpleNamespace(get_model_info=lambda: "qwen3-test"))
        assert "현재 모델:** qwen3-test" in _invoke(host, "_cmd_model", [])

        broken = SimpleNamespace(get_model_info=lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert "가져올 수 없습니다" in _invoke(_Host(model=broken), "_cmd_model", [])


# ─── /status ─────────────────────────────────────────────────────


class TestStatusCommand:
    def test_status_with_full_dependencies(self, session_stub: SessionStub) -> None:
        from unittest.mock import MagicMock

        session_stub.get_session_info = lambda: {
            "id": "sess-1",
            "turn_count": 2,
            "message_count": 4,
            "memory_keys": ["a", "b"],
        }
        tools = MagicMock()
        tools.__len__ = _tool_count
        shaper = SimpleNamespace(get_stats=lambda: {"total_shaped": 9})
        host = _Host(session=session_stub, tools=tools, shaper=shaper)

        out = _invoke(host, "_cmd_status", [])

        assert "**세션:** sess-1" in out
        assert "**도구:** 7개 등록됨" in out
        assert "**압축 횟수:** 9회" in out


# ─── /compact · /session ─────────────────────────────────────────


class TestCompactAndSession:
    def test_compact_requires_both_dependencies(self) -> None:
        assert "not connected" in _invoke(_Host(), "_cmd_compact", [])
        assert "not connected" in _invoke(_Host(shaper=object()), "_cmd_compact", [])

    def test_compact_reports_reduction(self, session_stub: SessionStub) -> None:
        shaper = SimpleNamespace(
            shape=_shape_messages,
            _estimate_tokens=_estimate_tokens,
        )
        saved: dict[str, bool] = {}
        session_stub.save = lambda: saved.update(done=True)
        host = _Host(session=session_stub, shaper=shaper)

        out = _invoke(host, "_cmd_compact", [])

        assert "메시지: 1 → 1" in out
        assert saved.get("done") is True

    def test_session_subcommands_flow(self, session_stub: SessionStub) -> None:
        help_host = _Host(session=session_stub)
        assert "슬래시 커맨드" in _invoke(help_host, "_cmd_session", [])

        session_stub.list_sessions = lambda: []
        host = _Host(session=session_stub)
        assert "저장된 세션이 없습니다" in _invoke(host, "_cmd_session", ["list"])

        session_stub.list_sessions = lambda: [{"id": "s1", "turn_count": 3, "project_path": "/tmp/p"}]
        out = _invoke(host, "_cmd_session", ["list"])
        assert "`s1`" in out and "/tmp/p" in out

        saved: dict[str, bool] = {}
        session_stub.save = lambda: saved.update(ok=True)
        assert "저장되었습니다" in _invoke(host, "_cmd_session", ["save"])

        session_stub.load_session = lambda sid: sid == "s1"
        assert "로드되었습니다" in _invoke(host, "_cmd_session", ["load", "s1"])
        assert "찾을 수 없습니다" in _invoke(host, "_cmd_session", ["load", "zzz"])

        session_stub.get_session_info = lambda: {"id": "s1"}
        assert "id: s1" in _invoke(host, "_cmd_session", ["info"])

        session_stub.get_session_info = lambda: None
        assert "활성 세션이 없습니다" in _invoke(host, "_cmd_session", ["info"])
        assert "알 수 없는 세션 명령" in _invoke(host, "_cmd_session", ["wat"])


# ─── /resume (durable checkpoint) ────────────────────────────────


class TestResumeCommand:
    @pytest.fixture(autouse=True)
    def _isolate_cwd(self: TestResumeCommand, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.chdir(tmp_path)

    def _seed_checkpoint(self, trace_id: str = "tr-1") -> None:
        conn = sqlite3.connect(".agk_context.db")
        _ = conn.execute(
            "CREATE TABLE checkpoints (trace_id TEXT, label TEXT, state TEXT,"
            + " task_type TEXT, timestamp TEXT, context TEXT)"
        )
        _ = conn.execute(
            "INSERT INTO checkpoints VALUES (?, ?, ?, ?, ?, ?)",
            (
                trace_id,
                "step-1",
                "AWAITING_INPUT",
                "chat",
                "2026-08-25T00:00:00",
                json.dumps({"messages": [{"role": "user", "content": "이어서"}]}),
            ),
        )
        conn.commit()
        conn.close()

    def test_no_database_yields_friendly_message(self) -> None:
        host = _Host()

        assert "아직 생성되지 않았거나" in _invoke(host, "_cmd_resume", [])

    def test_resume_restores_latest_checkpoint(self) -> None:
        self._seed_checkpoint("tr-9")
        restored: dict[str, bool] = {}

        @final
        class Session:
            _current_session: JsonObject = {"messages": []}
            save: Callable[[], None] = staticmethod(lambda: restored.update(ok=True))

        out = _invoke(_Host(session=Session()), "_cmd_resume", [])

        assert "tr-9" in out
        assert "1개 복원됨" in out
        assert restored.get("ok") is True

    def test_resume_specific_trace_id(self) -> None:
        self._seed_checkpoint("tr-target")

        out = _invoke(_Host(), "_cmd_resume", ["tr-target"])

        assert "tr-target" in out


# ─── /project ────────────────────────────────────────────────────


class TestProjectCommand:
    def test_usage_without_args(self) -> None:
        assert _invoke(_Host(), "_cmd_project", []) == "Usage: `/project <folder_path>`"

    def test_scaffolds_conductor_structure(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        target = tmp_path / "newproj"
        registered: dict[str, str] = {}
        started: dict[str, str] = {}

        class Registry:
            def set_project_root(self, path: str) -> None:
                registered["path"] = path

        class Session:
            def start_session(self, project_path: str, resume: bool) -> None:
                _ = resume
                started["path"] = project_path

        host = _Host(tools=Registry(), session=Session())
        monkeypatch.chdir(tmp_path)

        out = _invoke(host, "_cmd_project", [target.name])

        assert "성공적으로 설정" in out
        assert registered["path"].endswith("newproj")
        assert started["path"].endswith("newproj")
        for fname in ("product.md", "tech-stack.md", "workflow.md", "tracks.md"):
            assert (target / "conductor" / fname).exists()
