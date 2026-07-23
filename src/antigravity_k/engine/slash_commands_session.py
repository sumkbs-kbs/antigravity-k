"""Session/context slash command handlers (mixin).

Provides: /help, /tools, /context, /memory, /model, /status, /compact,
/session, /resume, /project.

These handlers access ``self._session_manager``, ``self._context_shaper``,
``self._tool_registry``, and ``self._model_manager`` which are initialized by
``SlashCommandRegistryBase.__init__``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SlashCommandSessionMixin:
    """Session and context management command handlers.

    Note: The following attributes are provided by ``SlashCommandRegistryBase``
    via cooperative multiple inheritance (MRO).
    """

    # Mixin-required attributes (resolved via MRO at runtime)
    _commands: dict[str, Any]
    _tool_registry: Any
    _session_manager: Any
    _context_shaper: Any
    _model_manager: Any

    def _cmd_help(self, args: list) -> str:
        """도움말 표시."""
        lines = ["📚 **Antigravity-K 슬래시 커맨드**", ""]

        categories: dict[str, list] = {}
        for cmd in self._commands.values():
            categories.setdefault(cmd.category, []).append(cmd)

        for cat, cmds in sorted(categories.items()):
            lines.append(f"### {cat.upper()}")
            for cmd in sorted(cmds, key=lambda c: c.name):
                lines.append(f"  `{cmd.usage}` — {cmd.description}")
            lines.append("")

        return "\n".join(lines)

    def _cmd_tools(self, args: list) -> str:
        """도구 목록 표시."""
        if not self._tool_registry:
            return "Tool registry not connected."

        lines = ["🔧 **등록된 도구 목록**", ""]

        tools = self._tool_registry.get_all()
        if args:
            tools = [t for t in tools if t.category.value == args[0]]

        for tool in tools:
            risk_icon = {
                "safe": "🟢",
                "low": "🟡",
                "medium": "🟠",
                "high": "🔴",
                "critical": "⛔",
            }.get(tool.risk_level.value, "⚪")
            lines.append(f"  {tool.icon} `{tool.name}` {risk_icon} — {tool.description[:60]}")

        lines.append(f"\n총 {len(tools)}개 도구 등록됨")
        return "\n".join(lines)

    def _cmd_context(self, args: list) -> str:
        """컨텍스트 토큰 사용량 분석."""
        if not self._context_shaper:
            return "Context shaper not connected."
        if not self._session_manager:
            return "Session manager not connected."

        messages = self._session_manager.get_messages()
        usage = self._context_shaper.get_token_usage(messages)
        stats = self._context_shaper.get_stats()

        bar_len = 20
        filled = int(bar_len * usage["usage_pct"] / 100)
        bar = "█" * filled + "░" * (bar_len - filled)

        lines = [
            "📊 **컨텍스트 토큰 사용량**",
            "",
            f"  [{bar}] {usage['usage_pct']}%",
            f"  사용: {usage['total_tokens']:,} / {usage['max_tokens']:,} tokens",
            f"  잔여: {usage['budget_remaining']:,} tokens",
            "",
            "  **역할별 사용량:**",
        ]
        for role, tokens in sorted(usage["by_role"].items()):
            lines.append(f"    {role}: {tokens:,} tokens")

        lines.extend(
            [
                "",
                "  **압축 통계:**",
                f"    총 압축: {stats.get('total_shaped', 0)}회",
                f"    절약 토큰: {stats.get('tokens_saved', 0):,}",
                f"    콘텐츠 축소: {stats.get('collapses', 0)}건",
            ]
        )
        return "\n".join(lines)

    def _cmd_memory(self, args: list) -> str:
        """Working Memory 조회."""
        if not self._session_manager:
            return "Session manager not connected."

        if args:
            value = self._session_manager.get_memory(args[0])
            if value is None:
                return f"Memory key '{args[0]}' not found."
            return f"**{args[0]}:** {value}"

        memory = self._session_manager.get_all_memory()
        if not memory:
            return "Working Memory is empty."

        lines = ["🧠 **Working Memory**", ""]
        for key, value in memory.items():
            val_str = str(value)[:100]
            lines.append(f"  `{key}`: {val_str}")
        return "\n".join(lines)

    def _cmd_model(self, args: list) -> str:
        """모델 정보/변경."""
        if not self._model_manager:
            return "Model manager not connected."

        if args:
            try:
                self._model_manager.set_model(args[0])
                return f"✅ 모델이 `{args[0]}`로 변경되었습니다."
            except Exception as e:
                logger.exception("Unhandled exception")
                return f"모델 변경 실패: {e}"

        try:
            info = self._model_manager.get_model_info()
            return f"🤖 **현재 모델:** {info}"
        except Exception:
            logger.exception("Unhandled exception")
            return "모델 정보를 가져올 수 없습니다."

    def _cmd_status(self, args: list) -> str:
        """전체 상태 요약."""
        lines = ["⚡ **Antigravity-K 상태**", ""]

        if self._session_manager:
            info = self._session_manager.get_session_info()
            if info:
                lines.extend(
                    [
                        f"  **세션:** {info['id']}",
                        f"  **턴 수:** {info['turn_count']}",
                        f"  **메시지:** {info['message_count']}",
                        f"  **메모리 키:** {len(info['memory_keys'])}개",
                        "",
                    ]
                )

        if self._tool_registry:
            lines.append(f"  **도구:** {len(self._tool_registry)}개 등록됨")

        if self._context_shaper:
            stats = self._context_shaper.get_stats()
            lines.append(f"  **압축 횟수:** {stats.get('total_shaped', 0)}회")
            lines.append("")

        try:
            from antigravity_k.engine.tracing import AgentTracer

            readiness = AgentTracer.get_readiness_score()  # type: ignore[attr-defined]
            status_emoji = (
                "🟢" if readiness["status"] == "ready" else "🟡" if readiness["status"] == "degraded" else "🔴"
            )
            lines.append(
                f"  {status_emoji} **시스템 준비도(Readiness):** {readiness['score']}/100 ({readiness['status']})",
            )
        except Exception:
            logger.exception("Unhandled exception")

        return "\n".join(lines)

    def _cmd_compact(self, args: list) -> str:
        """수동 컨텍스트 압축."""
        if not self._context_shaper or not self._session_manager:
            return "Context shaper or session manager not connected."

        messages = self._session_manager.get_messages()
        original_count = len(messages)
        shaped = self._context_shaper.shape(messages)
        self._session_manager._current_session["messages"] = shaped
        self._session_manager.save()

        return (
            f"✅ 컨텍스트 압축 완료!\n"
            f"  메시지: {original_count} → {len(shaped)}\n"
            f"  토큰: {self._context_shaper._estimate_tokens(messages)} → "
            f"{self._context_shaper._estimate_tokens(shaped)}"
        )

    def _cmd_session(self, args: list) -> str:
        """세션 관리."""
        if not self._session_manager:
            return "Session manager not connected."
        if not args:
            return self._cmd_help(["session"])

        sub = args[0]
        if sub == "list":
            sessions = self._session_manager.list_sessions()
            if not sessions:
                return "저장된 세션이 없습니다."
            lines = ["📁 **세션 목록**", ""]
            for s in sessions:
                lines.append(f"  `{s['id']}` — 턴: {s['turn_count']}, 경로: {s['project_path']}")
            return "\n".join(lines)
        elif sub == "save":
            self._session_manager.save()
            return "✅ 세션이 저장되었습니다."
        elif sub == "load" and len(args) > 1:
            success = self._session_manager.load_session(args[1])
            if success:
                return f"✅ 세션 `{args[1]}`이 로드되었습니다."
            return f"세션 `{args[1]}`을 찾을 수 없습니다."
        elif sub == "info":
            info = self._session_manager.get_session_info()
            if not info:
                return "현재 활성 세션이 없습니다."
            lines = ["📋 **세션 정보**", ""]
            for k, v in info.items():
                lines.append(f"  {k}: {v}")
            return "\n".join(lines)
        return f"알 수 없는 세션 명령: {sub}"

    def _cmd_resume(self, args: list) -> str:
        """Durable Checkpoint 기반 상태 복구 및 재개."""
        import json
        import sqlite3

        db_path = ".agk_context.db"
        trace_id = args[0] if args else None

        try:
            with sqlite3.connect(db_path) as conn:
                if trace_id:
                    cursor = conn.execute(
                        "SELECT * FROM checkpoints WHERE trace_id = ? ORDER BY timestamp DESC LIMIT 1",
                        (trace_id,),
                    )
                else:
                    cursor = conn.execute("SELECT * FROM checkpoints ORDER BY timestamp DESC LIMIT 1")
                row = cursor.fetchone()

            if not row:
                return "❌ 복구할 수 있는 체크포인트를 찾지 못했습니다."

            recovered_trace_id = row[0]
            label = row[1]
            state = row[2]
            task_type = row[3]
            context_json = json.loads(row[5])

            if self._session_manager and "messages" in context_json:
                self._session_manager._current_session["messages"] = context_json["messages"]
                self._session_manager.save()

            return (
                f"✅ **[Durable Recovery 성공]**\n\n"
                f"- **Trace ID**: `{recovered_trace_id}`\n"
                f"- **Checkpoint**: `{label}`\n"
                f"- **State**: `{state}`\n"
                f"- **Task Type**: `{task_type}`\n"
                f"- **Messages**: {len(context_json.get('messages', []))}개 복원됨\n\n"
                f"컨텍스트가 성공적으로 복원되었습니다. 작업을 이어서 진행할 수 있습니다."
            )
        except sqlite3.OperationalError:
            return "❌ 체크포인트 데이터베이스(`.agk_context.db`)가 아직 생성되지 않았거나 존재하지 않습니다."
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"❌ 체크포인트 복구 중 오류 발생: {str(e)}"

    def _cmd_project(self, args: list) -> str:
        """프로젝트 초기화 및 샌드박싱."""
        import os

        if not args:
            return "Usage: `/project <folder_path>`"

        folder_path = os.path.abspath(args[0])

        try:
            os.makedirs(folder_path, exist_ok=True)
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"❌ 폴더 생성 실패: {e}"

        if self._tool_registry:
            self._tool_registry.set_project_root(folder_path)

        if self._session_manager:
            self._session_manager.start_session(project_path=folder_path, resume=False)

        conductor_dir = os.path.join(folder_path, "conductor")
        os.makedirs(conductor_dir, exist_ok=True)

        files_to_create = {
            "product.md": "# Product Definition\n\n프로젝트의 목표와 정의를 작성하세요.\n",
            "tech-stack.md": "# Tech Stack\n\n사용 기술 스택 정의.\n",
            "workflow.md": "# Workflow\n\n개발 및 검증 워크플로우 정의.\n",
            "tracks.md": "# Tracks Registry\n\n진행 중인 트랙 목록.\n",
        }

        for fname, content in files_to_create.items():
            fpath = os.path.join(conductor_dir, fname)
            if not os.path.exists(fpath):
                try:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content)
                except Exception:
                    logger.exception("Failed to create scaffolding file %s", fpath)

        return (
            f"✅ 프로젝트가 성공적으로 설정되었습니다!\n\n"
            f"**디렉토리:** `{folder_path}`\n"
            f"**샌드박스:** 활성화됨 (이 폴더 밖의 파일 수정은 엄격히 차단됩니다.)\n"
            f"**스캐폴딩:** `conductor/` 구조 생성 완료.\n\n"
            f"이제 이 폴더 내에서 안전하게 작업을 진행할 수 있습니다."
        )
