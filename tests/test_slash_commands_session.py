"""테스트: 세션 슬래시 커맨드 핸들러 (/help /tools /context /memory 등).
============================================================
각 핸들러의 미연결 가드, 렌더링 계약, 서브커맨드 분기를 검증한다.
"""

import json
import sqlite3
from types import SimpleNamespace

import pytest

from antigravity_k.engine.slash_commands_session import SlashCommandSessionMixin


def _tool(name="read_file", category="file", risk="safe", icon="📄", desc="파일 읽기"):
    return SimpleNamespace(
        name=name,
        category=SimpleNamespace(value=category),
        risk_level=SimpleNamespace(value=risk),
        icon=icon,
        description=desc,
    )


def _command(name="tools", category="session", usage="/tools", description="도구 목록"):
    return SimpleNamespace(name=name, category=category, usage=usage, description=description)


class _Host(SlashCommandSessionMixin):
    def __init__(self, *, commands=None, tools=None, session=None, shaper=None, model=None):
        self._commands = commands or {}
        self._tool_registry = tools
        self._session_manager = session
        self._context_shaper = shaper
        self._model_manager = model


@pytest.fixture
def session_stub():
    return SimpleNamespace(
        get_messages=lambda: [{"role": "user", "content": "hi"}],
        get_memory=lambda key: {"lang": "ko"}.get(key),
        get_all_memory=lambda: {},
        get_session_info=lambda: None,
        list_sessions=lambda: [],
        save=lambda: None,
        _current_session={"messages": []},
    )


# ─── /help · /tools ──────────────────────────────────────────────


class TestHelpAndTools:
    def test_help_groups_by_category_sorted(self):
        host = _Host(
            commands={
                "b": _command("beta", "agent", usage="/beta"),
                "a": _command("alpha", "agent", usage="/alpha"),
                "t": _command("tools", "session", usage="/tools"),
            }
        )

        out = host._cmd_help([])

        assert "### AGENT" in out and "### SESSION" in out
        assert out.index("`/alpha`") < out.index("`/beta`")
        assert "`/tools`" in out

    def test_tools_without_registry(self):
        assert _Host()._cmd_tools([]) == "Tool registry not connected."

    def test_tools_lists_with_risk_icons_and_count(self):
        host = _Host(
            tools=SimpleNamespace(
                get_all=lambda: [
                    _tool("safe_tool", risk="safe"),
                    _tool(name="mystery", risk="weird"),
                ]
            )
        )

        out = host._cmd_tools([])

        assert "`safe_tool` 🟢" in out
        assert "`mystery` ⚪" in out
        assert "총 2개 도구 등록됨" in out

    def test_tools_category_filter(self):
        host = _Host(
            tools=SimpleNamespace(
                get_all=lambda: [
                    _tool("reader", category="file"),
                    _tool("searcher", category="search"),
                ]
            )
        )

        out = host._cmd_tools(["file"])

        assert "`reader`" in out
        assert "`searcher`" not in out


# ─── /context ────────────────────────────────────────────────────


class TestContextCommand:
    def test_missing_shaper_or_session(self):
        assert _Host(shaper=None, session=object())._cmd_context([]) == ("Context shaper not connected.")
        shaper = SimpleNamespace(get_token_usage=lambda m: {}, get_stats=lambda: {})
        assert _Host(shaper=shaper)._cmd_context([]) == "Session manager not connected."

    def test_full_render_includes_bar_and_roles(self, session_stub):
        shaper = SimpleNamespace(
            get_token_usage=lambda m: {
                "usage_pct": 50,
                "total_tokens": 1000,
                "max_tokens": 2000,
                "budget_remaining": 1000,
                "by_role": {"system": 800, "user": 200},
            },
            get_stats=lambda: {"total_shaped": 3, "tokens_saved": 500, "collapses": 1},
        )
        host = _Host(session=session_stub, shaper=shaper)

        out = host._cmd_context([])

        assert "█" * 10 in out and "░" * 10 in out
        assert "50%" in out
        assert "system: 800" in out
        assert "총 압축: 3회" in out


# ─── /memory · /model ────────────────────────────────────────────


class TestMemoryAndModel:
    def test_memory_key_lookup_hit_and_miss(self, session_stub):
        host = _Host(session=session_stub)

        assert host._cmd_memory(["lang"]) == "**lang:** ko"
        assert host._cmd_memory(["nope"]) == "Memory key 'nope' not found."

    def test_memory_empty_and_listing_truncates_long_values(self):
        class EmptySession:
            def get_all_memory(self):
                return {}

            def get_memory(self, key):
                return None

        assert _Host(session=EmptySession())._cmd_memory([]) == "Working Memory is empty."

        long_value = "x" * 250

        class Session:
            def get_all_memory(self):
                return {"big": long_value}

            def get_memory(self, key):
                return None

        out = _Host(session=Session())._cmd_memory([])
        assert long_value not in out
        assert "x" * 100 in out

    def test_memory_without_session_manager(self):
        assert _Host()._cmd_memory([]) == "Session manager not connected."

    def test_model_set_success_and_failure(self):
        manager = SimpleNamespace(set_model=lambda name: None)
        host = _Host(model=manager)

        assert "변경되었습니다" in host._cmd_model(["qwen3-test"])

        failing = SimpleNamespace(set_model=lambda name: (_ for _ in ()).throw(ValueError("없음")))
        out = _Host(model=failing)._cmd_model(["ghost"])
        assert "모델 변경 실패" in out

    def test_model_info_and_unavailable(self):
        host = _Host(model=SimpleNamespace(get_model_info=lambda: "qwen3-test"))
        assert "현재 모델:** qwen3-test" in host._cmd_model([])

        broken = SimpleNamespace(get_model_info=lambda: (_ for _ in ()).throw(RuntimeError("x")))
        assert "가져올 수 없습니다" in _Host(model=broken)._cmd_model([])


# ─── /status ─────────────────────────────────────────────────────


class TestStatusCommand:
    def test_status_with_full_dependencies(self, session_stub, monkeypatch):
        from unittest.mock import MagicMock

        session_stub.get_session_info = lambda: {
            "id": "sess-1",
            "turn_count": 2,
            "message_count": 4,
            "memory_keys": ["a", "b"],
        }
        tools = MagicMock()
        tools.__len__ = lambda self: 7
        shaper = SimpleNamespace(get_stats=lambda: {"total_shaped": 9})
        host = _Host(session=session_stub, tools=tools, shaper=shaper)

        out = host._cmd_status([])

        assert "**세션:** sess-1" in out
        assert "**도구:** 7개 등록됨" in out
        assert "**압축 횟수:** 9회" in out


# ─── /compact · /session ─────────────────────────────────────────


class TestCompactAndSession:
    def test_compact_requires_both_dependencies(self):
        assert "not connected" in _Host()._cmd_compact([])
        assert "not connected" in _Host(shaper=object())._cmd_compact([])

    def test_compact_reports_reduction(self, session_stub):
        shaper = SimpleNamespace(
            shape=lambda messages: messages[:1],
            _estimate_tokens=lambda messages: len(messages) * 10,
        )
        saved = {}
        session_stub.save = lambda: saved.update(done=True)
        host = _Host(session=session_stub, shaper=shaper)

        out = host._cmd_compact([])

        assert "메시지: 1 → 1" in out
        assert saved.get("done") is True

    def test_session_subcommands_flow(self, session_stub, monkeypatch):
        help_host = _Host(session=session_stub)
        assert "슬래시 커맨드" in help_host._cmd_session([])

        session_stub.list_sessions = lambda: []
        host = _Host(session=session_stub)
        assert "저장된 세션이 없습니다" in host._cmd_session(["list"])

        session_stub.list_sessions = lambda: [{"id": "s1", "turn_count": 3, "project_path": "/tmp/p"}]
        out = host._cmd_session(["list"])
        assert "`s1`" in out and "/tmp/p" in out

        saved = {}
        session_stub.save = lambda: saved.update(ok=True)
        assert "저장되었습니다" in host._cmd_session(["save"])

        session_stub.load_session = lambda sid: sid == "s1"
        assert "로드되었습니다" in host._cmd_session(["load", "s1"])
        assert "찾을 수 없습니다" in host._cmd_session(["load", "zzz"])

        session_stub.get_session_info = lambda: {"id": "s1"}
        assert "id: s1" in host._cmd_session(["info"])

        session_stub.get_session_info = lambda: None
        assert "활성 세션이 없습니다" in host._cmd_session(["info"])
        assert "알 수 없는 세션 명령" in host._cmd_session(["wat"])


# ─── /resume (durable checkpoint) ────────────────────────────────


class TestResumeCommand:
    @pytest.fixture(autouse=True)
    def _isolate_cwd(self, tmp_path, monkeypatch):
        monkeypatch.chdir(tmp_path)

    def _seed_checkpoint(self, trace_id="tr-1"):
        conn = sqlite3.connect(".agk_context.db")
        conn.execute(
            "CREATE TABLE checkpoints (trace_id TEXT, label TEXT, state TEXT,"
            " task_type TEXT, timestamp TEXT, context TEXT)"
        )
        conn.execute(
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

    def test_no_database_yields_friendly_message(self):
        host = _Host()

        assert "아직 생성되지 않았거나" in host._cmd_resume([])

    def test_resume_restores_latest_checkpoint(self, session_stub):
        self._seed_checkpoint("tr-9")
        restored = {}

        class Session:
            _current_session = {"messages": []}
            save = staticmethod(lambda: restored.update(ok=True))

        out = _Host(session=Session())._cmd_resume([])

        assert "tr-9" in out
        assert "1개 복원됨" in out
        assert restored.get("ok") is True

    def test_resume_specific_trace_id(self):
        self._seed_checkpoint("tr-target")

        out = _Host()._cmd_resume(["tr-target"])

        assert "tr-target" in out


# ─── /project ────────────────────────────────────────────────────


class TestProjectCommand:
    def test_usage_without_args(self):
        assert _Host()._cmd_project([]) == "Usage: `/project <folder_path>`"

    def test_scaffolds_conductor_structure(self, tmp_path, monkeypatch):
        target = tmp_path / "newproj"
        registered = {}
        started = {}

        class Registry:
            def set_project_root(self, path):
                registered["path"] = path

        class Session:
            def start_session(self, project_path, resume):
                started["path"] = project_path

        host = _Host(tools=Registry(), session=Session())
        monkeypatch.chdir(tmp_path)

        out = host._cmd_project([target.name])

        assert "성공적으로 설정" in out
        assert registered["path"].endswith("newproj")
        assert started["path"].endswith("newproj")
        for fname in ("product.md", "tech-stack.md", "workflow.md", "tracks.md"):
            assert (target / "conductor" / fname).exists()
