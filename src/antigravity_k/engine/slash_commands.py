"""SlashCommands — 슬래시 커맨드 레지스트리.

==========================================
Claw Code의 CommandRegistry 아키텍처 이식.

에이전트 세션을 제어하는 `/` 접두사 명령어 시스템.
채팅 입력에서 `/`로 시작하는 명령을 감지하여 처리합니다.

사용 예:
    registry = SlashCommandRegistry(...)
    if registry.is_command("/tools"):
        result = registry.execute("/tools")
"""

import logging
from collections.abc import Callable

logger = logging.getLogger(__name__)


class SlashCommand:
    """슬래시 커맨드 정의."""

    def __init__(
        self,
        name: str,
        description: str,
        handler: Callable,
        usage: str = "",
        category: str = "general",
    ):
        """Initialize the SlashCommand.

        Args:
            name (str): str name.
            description (str): str description.
            handler (Callable): Callable handler.
            usage (str): str usage.
            category (str): str category.

        """
        self.name = name
        self.description = description
        self.handler = handler
        self.usage = usage or f"/{name}"
        self.category = category


class SlashCommandRegistry:
    """슬래시 커맨드 중앙 레지스트리.

    Claw Code의 CommandRegistry 패턴:
    - /help, /tools, /context, /memory, /model, /status, /compact, /session
    """

    def __init__(
        self,
        tool_registry=None,
        session_manager=None,
        context_shaper=None,
        model_manager=None,
        skill_loader=None,
        mode_manager=None,
    ) -> None:
        """Initialize the SlashCommandRegistry.

        Args:
            tool_registry: tool registry.
            session_manager: session manager.
            context_shaper: context shaper.
            model_manager: model manager.
            skill_loader: skill loader.
            mode_manager: mode manager (Plan/Build/Interactive).

        """
        self._commands: dict[str, SlashCommand] = {}
        self._tool_registry = tool_registry
        self._session_manager = session_manager
        self._context_shaper = context_shaper
        self._model_manager = model_manager
        self._skill_loader = skill_loader
        self._mode_manager = mode_manager

        # 기본 커맨드 등록
        self._register_defaults()

    def _register_defaults(self):
        """기본 슬래시 커맨드를 등록합니다."""
        self.register(
            SlashCommand(
                name="help",
                description="사용 가능한 슬래시 커맨드 목록을 표시합니다.",
                handler=self._cmd_help,
                usage="/help",
                category="general",
            ),
        )

        self.register(
            SlashCommand(
                name="tools",
                description="등록된 도구 목록과 상태를 표시합니다.",
                handler=self._cmd_tools,
                usage="/tools [category]",
                category="tools",
            ),
        )

        self.register(
            SlashCommand(
                name="context",
                description="현재 컨텍스트 토큰 사용량을 분석합니다.",
                handler=self._cmd_context,
                usage="/context",
                category="context",
            ),
        )

        self.register(
            SlashCommand(
                name="memory",
                description="세션 Working Memory 내용을 조회합니다.",
                handler=self._cmd_memory,
                usage="/memory [key]",
                category="session",
            ),
        )

        self.register(
            SlashCommand(
                name="model",
                description="현재 모델 정보를 확인하거나 변경합니다.",
                handler=self._cmd_model,
                usage="/model [model_name]",
                category="model",
            ),
        )

        self.register(
            SlashCommand(
                name="status",
                description="에이전트 전체 상태를 요약합니다.",
                handler=self._cmd_status,
                usage="/status",
                category="general",
            ),
        )

        self.register(
            SlashCommand(
                name="self",
                description="현재 런타임 기준으로 Antigravity-K가 할 수 있는 일과 한계를 표시합니다.",
                handler=self._cmd_self,
                usage="/self",
                category="general",
            ),
        )

        self.register(
            SlashCommand(
                name="compact",
                description="수동으로 컨텍스트 압축을 트리거합니다.",
                handler=self._cmd_compact,
                usage="/compact",
                category="context",
            ),
        )

        self.register(
            SlashCommand(
                name="session",
                description="세션 관리 (list/save/load/info).",
                handler=self._cmd_session,
                usage="/session [list|save|load <id>|info]",
                category="session",
            ),
        )

        self.register(
            SlashCommand(
                name="project",
                description="새 프로젝트를 초기화하고 해당 폴더로 컨텍스트를 바인딩합니다.",
                handler=self._cmd_project,
                usage="/project <folder_path>",
                category="session",
            ),
        )

        self.register(
            SlashCommand(
                name="resume",
                description="최신 DB 체크포인트에서 상태를 복구하여 작업을 이어서 진행합니다.",
                handler=self._cmd_resume,
                usage="/resume [trace_id]",
                category="session",
            ),
        )

        self.register(
            SlashCommand(
                name="approve",
                description="대기 중인 도구 실행을 승인합니다.",
                handler=self._cmd_approve,
                usage="/approve <tool_name>",
                category="system",
            ),
        )

        self.register(
            SlashCommand(
                name="browse",
                description="특화된 서브 에이전트를 통해 웹 브라우저를 자율 탐색합니다.",
                handler=self._cmd_browse,
                usage="/browse <url> [지시사항]",
                category="system",
            ),
        )

        self.register(
            SlashCommand(
                name="skill",
                description="특정 스킬(Markdown 지침서)을 에이전트 시스템 프롬프트에 주입하거나 관리합니다.",
                handler=self._cmd_skill,
                usage="/skill [list|activate <id>|deactivate <id>|clear]",
                category="system",
            ),
        )

        self.register(
            SlashCommand(
                name="qa",
                description="DOM 파싱 도구를 사용해 대시보드 UI를 자가 점검합니다.",
                handler=self._cmd_qa,
                usage="/qa [url]",
                category="system",
            ),
        )

        self.register(
            SlashCommand(
                name="evolve",
                description="본 프로그램 스스로 코드를 수정, 검증하고 문서를 업데이트하는 메타 진화를 수행합니다.",
                handler=self._cmd_evolve,
                usage="/evolve <기능 고도화 요구사항>",
                category="autonomy",
            ),
        )

        self.register(
            SlashCommand(
                name="goal",
                description="자율 목표를 성공 기준, 실행 루프, 검증 게이트로 변환합니다.",
                handler=self._cmd_goal,
                usage="/goal <objective>",
                category="autonomy",
            ),
        )

        self.register(
            SlashCommand(
                name="agentic",
                description="최신 에이전틱 기술 레이더와 Antigravity-K 업그레이드 우선순위를 표시합니다.",
                handler=self._cmd_agentic,
                usage="/agentic [objective]",
                category="autonomy",
            ),
        )

        self.register(
            SlashCommand(
                name="mcp",
                description="MCP 최신 기능 레이더, 서버 설정 감사, 안전 템플릿을 표시합니다.",
                handler=self._cmd_mcp,
                usage="/mcp [radar|audit <path>|template]",
                category="tools",
            ),
        )

        self.register(
            SlashCommand(
                name="market",
                description="Skill Marketplace: search, install, remove, list, info, update skills.",
                handler=self._cmd_market,
                usage="/market [search|install|remove|list|info|update]",
                category="tools",
            ),
        )

        self.register(
            SlashCommand(
                name="mode",
                description="현재 실행 모드(Plan/Build/Interactive) 상태를 표시하거나 변경합니다.",
                handler=self._cmd_mode,
                usage="/mode [plan|build|interactive|status]",
                category="system",
            ),
        )

        self.register(
            SlashCommand(
                name="plan",
                description="Plan 모드로 전환합니다. 읽기 전용 도구만 허용됩니다.",
                handler=self._cmd_plan,
                usage="/plan [이유]",
                category="system",
            ),
        )

        self.register(
            SlashCommand(
                name="build",
                description="Build 모드로 전환합니다. 모든 도구 실행이 허용됩니다.",
                handler=self._cmd_build,
                usage="/build [plan_artifact_path]",
                category="system",
            ),
        )

        self.register(
            SlashCommand(
                name="capabilities",
                description="현재 PC/도구/MCP/Skills의 자율 사용 가능 여부를 판단합니다.",
                handler=self._cmd_capabilities,
                usage="/capabilities [objective]",
                category="autonomy",
            ),
        )

        self.register(
            SlashCommand(
                name="codex",
                description="Codex식 강점과 운영 루프를 Antigravity-K 업그레이드 계약으로 변환합니다.",
                handler=self._cmd_codex,
                usage="/codex [objective]",
                category="autonomy",
            ),
        )

        self.register(
            SlashCommand(
                name="dialectic",
                description="Hegelion 변증법적 추론 (Thesis→Antithesis→Synthesis) 으로 문제를 심층 분석합니다.",
                handler=self._cmd_dialectic,
                usage="/dialectic <질문 또는 문제>",
                category="autonomy",
            ),
        )

        self.register(
            SlashCommand(
                name="finance",
                description="Financial Assistant 페르소나를 활성화하여 재무 분석 및 모델링을 수행합니다.",
                handler=self._cmd_finance,
                usage="/finance <분석 대상 및 상황>",
                category="finance",
            ),
        )

        self.register(
            SlashCommand(
                name="comps",
                description="유사기업비교(Comps) 분석을 수행합니다.",
                handler=self._cmd_finance,
                usage="/comps <기업명>",
                category="finance",
            ),
        )

        self.register(
            SlashCommand(
                name="dcf",
                description="DCF(현금흐름할인법) 가치평가 모델을 생성합니다.",
                handler=self._cmd_finance,
                usage="/dcf <기업명>",
                category="finance",
            ),
        )

        self.register(
            SlashCommand(
                name="aishell",
                description="자연어 지시를 파싱하여 터미널(Bash) 커맨드로 즉시 변환 후 실행합니다.",
                handler=self._cmd_aishell,
                usage="/aishell <명령어>",
                category="system",
            ),
        )

        self.register(
            SlashCommand(
                name="benchmark",
                description="collective-council vs 단일 모델 품질/속도 벤치마크를 실행하거나 누적 비교표를 출력합니다.",
                handler=self._cmd_benchmark,
                usage="/benchmark [run [suite|case-id] | report [suite] | clear]",
                category="system",
            ),
        )

        # Agent Skills: Lifecycle Commands
        def make_handler(cmd_name):
            return lambda args: self._cmd_lifecycle(cmd_name, args)

        lifecycle_commands = [
            ("spec", "Spec before code. Write a PRD covering objectives.", "lifecycle"),
            ("plan", "Small, atomic tasks. Decompose specs into implementable units.", "lifecycle"),
            ("build", "One slice at a time. Implement incrementally.", "lifecycle"),
            ("test", "Tests are proof. Red-Green-Refactor.", "lifecycle"),
            ("review", "Improve code health. Five-axis code review.", "lifecycle"),
            ("code-simplify", "Clarity over cleverness. Reduce complexity.", "lifecycle"),
            ("ship", "Faster is safer. Pre-launch checks and staged rollouts.", "lifecycle"),
        ]

        for name, desc, cat in lifecycle_commands:
            self.register(
                SlashCommand(
                    name=name,
                    description=desc,
                    handler=make_handler(name),
                    usage=f"/{name} [arguments]",
                    category=cat,
                ),
            )

    # ─────────── 레지스트리 API ───────────

    def register(self, command: SlashCommand):
        """커맨드를 등록합니다."""
        self._commands[command.name] = command

    def is_command(self, text: str) -> bool:
        """텍스트가 슬래시 커맨드인지 확인합니다."""
        if not text.startswith("/"):
            return False
        cmd_name = text.split()[0][1:]  # / 제거
        return cmd_name in self._commands

    def execute(self, text: str) -> str:
        """슬래시 커맨드를 실행하거나 자연어 의도를 처리합니다."""
        text = (text or "").strip()
        if not text:
            return "Error: Empty command."

        if not text.startswith("/"):
            return self._execute_natural_language(text)

        parts = text.split()
        if not parts:
            return "Error: Empty command."

        cmd_name = parts[0][1:]  # / 제거
        args = parts[1:]

        command = self._commands.get(cmd_name)
        if not command:
            return f"Unknown command: /{cmd_name}. Use /help to see available commands."

        try:
            return command.handler(args)
        except Exception as e:
            logger.error("Slash command error: %s", e, exc_info=True)
            return f"Error executing /{cmd_name}: {e}"

    def _execute_natural_language(self, text: str) -> str:
        """슬래시가 없는 자연어를 받아서 로컬 모델을 통해 자율적으로 도구를 실행하고 답변을 반환합니다."""
        from antigravity_k.engine.orchestrator import OrchestratorAgent

        if not self._model_manager:
            return "Error: Model manager is not available for natural language execution."

        info = self._model_manager.get_model_info()
        target_model = (
            info.get("active_model", "default") if isinstance(info, dict) else getattr(info, "active_model", "default")
        )
        if target_model == "default" or not target_model:
            # Fallback to whatever model is first or default in manager
            models = self._model_manager.list_models()
            if models:
                target_model = models[0].get("id")
            else:
                target_model = "local-model"

        orchestrator = OrchestratorAgent(model_manager=self._model_manager)

        messages = []
        if self._session_manager:
            session_msgs = self._session_manager.get_messages()
            # 마지막 5개 메시지만 문맥으로 전달
            messages = session_msgs[-5:] if len(session_msgs) > 5 else session_msgs

        messages.append({"role": "user", "content": text})

        try:
            return orchestrator.run_sync(messages, target_model=target_model)
        except Exception as e:
            logger.error("Natural language execution error: %s", e, exc_info=True)
            return f"자연어 처리 중 오류 발생: {e}"

    def get_completions(self, prefix: str) -> list[str]:
        """자동완성 후보를 반환합니다."""
        if not prefix.startswith("/"):
            return []
        search = prefix[1:]
        return [f"/{name}" for name in self._commands if name.startswith(search)]

    # ─────────── 기본 커맨드 핸들러 ───────────

    def _cmd_help(self, args: list) -> str:
        """도움말 표시."""
        lines = ["📚 **Antigravity-K 슬래시 커맨드**", ""]

        categories: dict[str, list[SlashCommand]] = {}
        for cmd in self._commands.values():
            categories.setdefault(cmd.category, []).append(cmd)

        for cat, cmds in sorted(categories.items()):
            lines.append(f"### {cat.upper()}")
            for cmd in sorted(cmds, key=lambda c: c.name):
                lines.append(f"  `{cmd.usage}` — {cmd.description}")
            lines.append("")

        return "\n".join(lines)

    def _cmd_self(self, args: list) -> str:
        """런타임 기반 자기 능력 보고서."""
        from antigravity_k.engine.self_capability import SelfCapabilityEngine

        engine = SelfCapabilityEngine()
        snapshot = engine.build(
            tool_registry=self._tool_registry,
            skill_loader=self._skill_loader,
            model_manager=self._model_manager,
            slash_commands=self._commands,
        )
        return engine.render_markdown(snapshot)

    def _cmd_tools(self, args: list) -> str:
        """도구 목록 표시."""
        if not self._tool_registry:
            return "Tool registry not connected."

        lines = ["🔧 **등록된 도구 목록**", ""]

        tools = self._tool_registry.get_all()
        if args:
            # 카테고리 필터
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
            ],
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
            # 모델 변경
            try:
                self._model_manager.set_model(args[0])
                return f"✅ 모델이 `{args[0]}`로 변경되었습니다."
            except Exception as e:
                logger.exception("Unhandled exception")
                return f"모델 변경 실패: {e}"

        # 현재 모델 정보
        try:
            info = self._model_manager.get_model_info()
            return f"🤖 **현재 모델:** {info}"
        except Exception:
            logger.exception("Unhandled exception")
            return "모델 정보를 가져올 수 없습니다."

    def _cmd_status(self, args: list) -> str:
        """전체 상태 요약."""
        lines = ["⚡ **Antigravity-K 상태**", ""]

        # 세션 정보
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
                    ],
                )

        # 도구 정보
        if self._tool_registry:
            lines.append(f"  **도구:** {len(self._tool_registry)}개 등록됨")

        # 컨텍스트 정보
        if self._context_shaper:
            stats = self._context_shaper.get_stats()
            lines.append(f"  **압축 횟수:** {stats.get('total_shaped', 0)}회")
            lines.append("")

        # AgentTracer Readiness Score 연결
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
            pass

        return "\n".join(lines)

    def _cmd_compact(self, args: list) -> str:
        """수동 컨텍스트 압축."""
        if not self._context_shaper or not self._session_manager:
            return "Context shaper or session manager not connected."

        messages = self._session_manager.get_messages()
        original_count = len(messages)

        shaped = self._context_shaper.shape(messages)

        # 세션 메시지 교체
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
                    cursor = conn.execute(
                        "SELECT * FROM checkpoints ORDER BY timestamp DESC LIMIT 1",
                    )
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

        # 1. 폴더 생성
        try:
            os.makedirs(folder_path, exist_ok=True)
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"❌ 폴더 생성 실패: {e}"

        # 2. ToolRegistry 및 PermissionGate 샌드박스 바인딩
        if self._tool_registry:
            self._tool_registry.set_project_root(folder_path)

        # 3. SessionManager 경로 연동 및 새 세션 시작
        if self._session_manager:
            self._session_manager.start_session(project_path=folder_path, resume=False)

        # 4. Conductor 스캐폴딩 생성
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

    def _cmd_qa(self, args: list) -> str:
        """대시보드 DOM 기반 자가 점검."""
        if not self._tool_registry or "fetch_dom" not in self._tool_registry._tools:
            return "❌ `fetch_dom` 도구가 레지스트리에 없습니다."

        url = args[0] if args else "http://127.0.0.1:8000/"

        # DOM 추출 도구 직접 실행 (Stateful 방식)
        tool = self._tool_registry._tools["fetch_dom"]

        # 1. 페이지 접속
        goto_res = tool.execute(action="goto", url=url)
        if "Error" in goto_res:
            return f"❌ QA 실패: 접속 중 오류 발생\n\n```text\n{goto_res}\n```"

        # 2. DOM 추출
        result = tool.execute(action="extract", selector="#app")

        # 3. 브라우저 세션 정리 (QA 명령어는 단발성이므로 닫기)
        tool.execute(action="close")

        if "Error" in result or "error" in result.lower() and "browser" in result.lower():
            return f"❌ QA 실패: DOM 추출 중 오류 발생\n\n```text\n{result}\n```"

        # 간단한 휴리스틱 검사
        report = []
        report.append(f"🔍 **QA 점검 보고서 ({url})**\n")

        # 1. 렌더링 확인
        if len(result) < 50:
            report.append("⚠️ **화면 빈 렌더링 의심:** DOM 텍스트가 너무 짧습니다.")
        else:
            report.append("✅ **화면 렌더링 정상:** DOM 요소 감지됨.")

        # 2. 에러 메시지 확인
        error_keywords = ["연결 실패", "에러", "500 Internal", "Cannot fetch"]
        found_errors = [kw for kw in error_keywords if kw in result]
        if found_errors:
            report.append(
                f"❌ **UI 에러 발생:** 화면 내에 다음 에러 키워드가 포함되어 있습니다: {', '.join(found_errors)}",
            )
        else:
            report.append("✅ **UI 에러 없음:** 화면 내 치명적 에러 문구 미검출.")

        # 3. 모델 드롭다운 확인 (qwen, deepseek, llama 등)
        model_keywords = ["qwen", "deepseek", "llama", "phi"]
        found_models = [kw for kw in model_keywords if kw.lower() in result.lower()]
        if found_models:
            report.append(
                f"✅ **모델 로드 확인:** 드롭다운 내 다음 모델들이 발견됨: {', '.join(found_models)}",
            )
        else:
            report.append("⚠️ **모델 미발견:** 화면에서 설치된 로컬 모델 목록을 찾을 수 없습니다.")

        report.append("\n**추출된 DOM 텍스트 요약 (최대 300자):**")
        report.append(f"```text\n{result[:300]}...\n```")

        return "\n".join(report)

    def _cmd_goal(self, args: list) -> str:
        """자율 목표 계약 생성."""
        objective = " ".join(args).strip()
        if not objective:
            objective = ""

        context = {}
        if self._session_manager:
            try:
                context["session"] = self._session_manager.get_session_info()
            except Exception:
                logger.exception("Unhandled exception")
                context["session"] = "unavailable"
        if self._tool_registry:
            try:
                context["tool_count"] = len(self._tool_registry)
            except Exception:
                logger.exception("Unhandled exception")
                context["tool_count"] = "unknown"

        from antigravity_k.engine.goal_runner import GoalRunner

        runner = GoalRunner()
        report = runner.run(objective, context=context)
        return runner.render_markdown(report)

    def _cmd_agentic(self, args: list) -> str:
        """최신 에이전틱 기술 레이더."""
        objective = " ".join(args).strip()
        from antigravity_k.engine.agentic_tech_radar import AgenticTechRadar

        radar = AgenticTechRadar()
        report = radar.evaluate(objective)
        return radar.render_markdown(report)

    def _cmd_mcp(self, args: list) -> str:
        """MCP 최신 기능 레이더 및 설정 감사."""
        from antigravity_k.engine.mcp_capability import MCPCapabilityAdvisor

        advisor = MCPCapabilityAdvisor()
        subcommand = args[0].lower() if args else "radar"

        if subcommand == "template":
            return "```json\n" + advisor.render_template() + "\n```"

        if subcommand == "audit" or subcommand.endswith(".json"):
            path = args[1] if subcommand == "audit" and len(args) > 1 else subcommand
            if subcommand == "audit" and len(args) <= 1:
                path = ".mcp.json"
            config = advisor.load_config(path)
            report = advisor.audit_config(config, source=path)
            return advisor.render_markdown(report)

        if subcommand in {"radar", "capabilities", "latest"}:
            report = advisor.audit_config({}, source="latest-capability-radar")
            return advisor.render_markdown(report)

        return "Usage: `/mcp [radar|audit <path>|template]`"

    def _cmd_market(self, args: list) -> str:
        """Skill Marketplace 명령어."""
        try:
            from antigravity_k.engine.skill_market_client import SkillMarketClient
            from antigravity_k.engine.skill_market_registry import SkillMarketRegistry
        except ImportError as e:
            return f"❌ Market dependencies not available: {e}"

        market_client = SkillMarketClient()
        registry = SkillMarketRegistry(
            project_root=".",
            market_client=market_client,
            skill_loader=self._skill_loader,
        )

        if not args:
            return (
                "📦 **Skill Marketplace**\n\n"
                "Usage: `/market <subcommand>`\n\n"
                "`/market search <query>` — Search for skills\n"
                "`/market install <package>` — Install a skill\n"
                "`/market remove <name>` — Remove an installed skill\n"
                "`/market list` — List installed skills\n"
                "`/market info <name>` — Show skill details\n"
                "`/market update [name]` — Update a skill (or all if name omitted)"
            )

        sub = args[0].lower()
        rest = args[1:]

        if sub == "search":
            query = " ".join(rest).strip()
            if not query:
                return "Usage: `/market search <query>`"
            results = registry.search(query)
            if isinstance(results, list) and results and "error" not in results[0]:
                return market_client.format_search_results(results)
            return "🔍 검색 결과가 없습니다."

        elif sub == "install":
            if not rest:
                return "Usage: `/market install <package>`"
            package = rest[0]
            result = registry.install(package)
            if result.get("success"):
                return f"✅ **Install complete**\n\n{result.get('summary', '')}"
            error = result.get("error", "Unknown error")
            warnings = result.get("warnings", [])
            msg = f"❌ Install failed: {error}"
            if warnings:
                msg += "\n\n**Warnings:**\n" + "\n".join(f"- {w}" for w in warnings)
            return msg

        elif sub == "remove":
            if not rest:
                return "Usage: `/market remove <name>`"
            name = rest[0]
            result = registry.remove(name)
            if result.get("success"):
                return f"✅ **Removed**\n\n{result.get('summary', '')}"
            return f"❌ Remove failed: {result.get('error', 'Unknown error')}"

        elif sub in ("list", "ls"):
            installed = registry.list_installed()
            return registry.format_list(installed)

        elif sub == "info":
            if not rest:
                return "Usage: `/market info <name>`"
            name = rest[0]
            skill_info = registry.get_info(name)
            if skill_info:
                return registry.format_info(skill_info)
            # 패키지명으로 직접 조회
            if name.startswith("@antigravity-k/skill-"):
                detail = market_client.get_detail(name)
                if detail:
                    lines = [
                        f"📦 **{detail.name}** `v{detail.version}`",
                        "",
                        f"설명: {detail.description}",
                        f"키워드: {', '.join(detail.keywords)}" if detail.keywords else "",
                        f"라이선스: {detail.license}" if detail.license else "",
                        f"npm: {detail.npm_url}" if detail.npm_url else "",
                    ]
                    if detail.is_agk_skill:
                        lines.extend(
                            [
                                "",
                                "**AGK 메타데이터:**",
                                f"  - 위험도: `{detail.agk_risk_level}`",
                                f"  - 신뢰수준: `{detail.agk_trust_level}`",
                                f"  - 승인필요: {'✅' if detail.agk_requires_approval else '❌'}",
                            ]
                        )
                        if detail.agk_mcp_server_id:
                            lines.append(f"  - MCP 서버: `{detail.agk_mcp_server_id}`")
                    return "\n".join(line for line in lines if line)
                return f"📦 `{name}`을(를) 찾을 수 없습니다."
            return f"❌ Skill `{name}`이(가) 설치되지 않았습니다."

        elif sub == "update":
            if rest:
                name = rest[0]
                result = registry.update(name)
                if result.get("success"):
                    return f"✅ **Updated**\n\n{result.get('summary', '')}"
                return f"❌ Update failed: {result.get('error', 'Unknown error')}"
            # name 생략 시 전체 업데이트
            results = registry.update_all()
            updated = [r for r in results if r.get("success")]
            if updated:
                lines = ["✅ **업데이트 완료**", ""]
                for r in updated:
                    lines.append(f"  - `{r.get('skill_name', '?')}` → `{r.get('version', '?')}`")
                return "\n".join(lines)
            return "✅ 모든 스킬이 최신 상태입니다."

        return f"❓ 알 수 없는 하위 명령: `{sub}`.\n" "사용 가능: search, install, remove, list, info, update"

    def _cmd_capabilities(self, args: list) -> str:
        """현재 등록된 capabilities의 자율 사용 가능성 표시."""
        objective = " ".join(args).strip()
        lines = [
            "# Autonomous Capability Manifest",
            "",
            f"**Objective:** `{objective or 'general'}`",
            "",
        ]

        if self._tool_registry is not None:
            lines.append(self._tool_registry.render_autonomous_policy().strip())
            lines.append("")
            decisions = self._tool_registry.get_autonomous_manifest(objective)
            counts = {
                "allow": sum(1 for item in decisions if item.decision == "allow"),
                "prompt": sum(1 for item in decisions if item.decision == "prompt"),
                "deny": sum(1 for item in decisions if item.decision == "deny"),
            }
            lines.append(
                f"**Tools/MCP:** allow={counts['allow']}, prompt={counts['prompt']}, deny={counts['deny']}",
            )
            lines.append("")
            if not decisions:
                lines.append(
                    "- Tool registry is connected, but no executable tools are registered yet.",
                )
            else:
                for decision in decisions[:30]:
                    lines.append(
                        f"- `{decision.capability_id}` [{decision.capability_type}] "
                        f"→ **{decision.decision}** "
                        f"(risk={decision.risk_level}, trust={decision.trust_level}) — {decision.reason}",
                    )
                if len(decisions) > 30:
                    lines.append(f"- ... {len(decisions) - 30} more capabilities")
        else:
            lines.append("**Tools/MCP:** Tool registry not connected.")

        if self._skill_loader is not None:
            skill_decisions = [
                decision for decision in self._skill_loader.get_autonomous_manifest(objective) if decision.score > 0
            ]
            lines.extend(["", "## Skills", ""])
            if not skill_decisions:
                lines.append("- No relevant skill candidates for this objective.")
            else:
                for decision in skill_decisions[:10]:
                    lines.append(
                        f"- `{decision.capability_id}` → **{decision.decision}** "
                        f"(score={decision.score}, risk={decision.risk_level}) — {decision.reason}",
                    )
        else:
            lines.extend(["", "**Skills:** Skill loader not connected."])

        return "\n".join(lines)

    def _cmd_codex(self, args: list) -> str:
        """Codex식 강점을 Antigravity-K 실행 계약으로 표시합니다."""
        objective = " ".join(args).strip()
        connected_tools = len(self._tool_registry) if self._tool_registry else 0
        known_skills = 0
        if self._skill_loader is not None:
            known_skills = len(self._skill_loader.get_autonomous_manifest(objective))

        from antigravity_k.engine.codex_transfer import CodexTransferEngine

        engine = CodexTransferEngine()
        report = engine.build(
            objective=objective,
            connected_tools=connected_tools,
            known_skills=known_skills,
        )
        return engine.render_markdown(report)

    def _cmd_mode(self, args: list) -> str:
        """/mode 명령어: 실행 모드 상태 표시 및 변경."""
        if not args:
            return self._mode_status()

        sub = args[0].lower()

        if sub == "status" or sub == "info":
            return self._mode_status()

        if sub == "plan":
            return self._mode_switch_plan(args[1:])

        if sub == "build":
            return self._mode_switch_build(args[1:])

        if sub == "interactive":
            return self._mode_switch_interactive()

        return "Usage: /mode [plan|build|interactive|status]"

    def _cmd_plan(self, args: list) -> str:
        """/plan 명령어: Plan 모드로 전환."""
        reason = " ".join(args).strip() if args else "사용자 요청 (/plan)"
        return self._mode_switch_plan(args if args else [reason])

    def _cmd_build(self, args: list) -> str:
        """/build 명령어: Build 모드로 전환."""
        return self._mode_switch_build(args)

    def _mode_status(self) -> str:
        """현재 모드 상태를 반환합니다."""
        if not hasattr(self, "_mode_manager") or self._mode_manager is None:
            # 모드 매니저가 없으면 engine_context에서 찾기
            return "ModeManager not connected. Use the main session to access mode control."

        return self._mode_manager.format_status()

    def _mode_switch_plan(self, args: list) -> str:
        """Plan 모드로 전환합니다."""
        if not hasattr(self, "_mode_manager") or self._mode_manager is None:
            return "ModeManager not connected."

        reason = " ".join(args).strip() if args else "사용자 요청 (/plan)"
        if self._mode_manager.switch_to_plan(reason):
            return f"✅ **PLAN 모드로 전환되었습니다.**\n\n{self._mode_manager.format_status()}"
        return "❌ PLAN 모드 전환에 실패했습니다."

    def _mode_switch_build(self, args: list) -> str:
        """Build 모드로 전환합니다."""
        if not hasattr(self, "_mode_manager") or self._mode_manager is None:
            return "ModeManager not connected."

        plan_path = args[0] if args else None
        reason = "사용자 요청 (/build)"

        if plan_path:
            self._mode_manager.set_plan_artifact(plan_path)
            self._mode_manager.set_plan_quality_passed(True)
            reason = f"Plan 아티팩트 '{plan_path}' 기반 Build 모드 전환"

        if self._mode_manager.switch_to_build(plan_artifact_path=plan_path, reason=reason):
            return f"✅ **BUILD 모드로 전환되었습니다.**\n\n{self._mode_manager.format_status()}"

        # 자동 전환 조건 불충족 시 안내
        if self._mode_manager.is_plan:
            msg = (
                "❌ BUILD 모드 전환에 실패했습니다.\n\n"
                "Plan → Build 자동 전환 조건이 충족되지 않았습니다:\n"
                "1. Plan 아티팩트(`implementation_plan.md`)가 생성되었는지 확인하세요.\n"
                "2. Plan 품질 검증(QualityGate)이 통과되어야 합니다.\n"
                "3. 강제 전환: `/build <plan_artifact_path>` 로 경로를 직접 지정할 수 있습니다."
            )
            return msg

        return "❌ BUILD 모드 전환에 실패했습니다."

    def _mode_switch_interactive(self) -> str:
        """Interactive 모드로 전환합니다."""
        if not hasattr(self, "_mode_manager") or self._mode_manager is None:
            return "ModeManager not connected."

        if self._mode_manager.switch_to_interactive("사용자 요청 (/mode interactive)"):
            return f"✅ **INTERACTIVE 모드로 전환되었습니다.**\n\n{self._mode_manager.format_status()}"
        return "❌ INTERACTIVE 모드 전환에 실패했습니다."

    def _cmd_approve(self, args: list) -> str:
        return "System command: /approve is managed by the orchestrator."

    def _cmd_browse(self, args: list) -> str:
        return "System command: /browse is managed by the orchestrator."

    def _cmd_skill(self, args: list) -> str:
        return "System command: /skill is managed by the orchestrator."

    def _cmd_evolve(self, args: list):
        if not self._model_manager:
            return "Error: Model manager is not connected."

        requirement = " ".join(args).strip()
        if not requirement:
            return "Usage: `/evolve <기능 고도화 요구사항>`"

        from antigravity_k.agents.meta_evolution_agent import MetaEvolutionAgent
        from antigravity_k.engine.orchestrator import OrchestratorAgent

        # 임시 툴 익스큐터 생성
        orch = OrchestratorAgent(
            model_manager=self._model_manager,
            tool_registry=self._tool_registry,
        )
        agent = MetaEvolutionAgent(
            model_manager=self._model_manager,
            tool_executor=orch.ctx.tool_executor,
        )

        # Generator 자체를 반환 (chat.py에서 스트리밍으로 소비됨)
        return agent.evolve(requirement)

    def _cmd_aishell(self, args: list) -> str:
        """자연어 의도를 받아 Bash 코드로 변환 후 실행합니다."""
        if not args:
            return "Usage: `/aishell <자연어 명령어>`"

        intent = " ".join(args)

        if not self._model_manager:
            return "❌ Error: Model manager is not connected."

        # 1. 의도를 프롬프트로 구성
        prompt = (
            f"Translate the following task to a macOS shell command. "
            f"Provide ONLY the command in ONE LINE, with no explanation:\n\n"
            f"Task: {intent}"
        )

        info = self._model_manager.get_model_info()
        target_model = (
            info.get("active_model", "default") if isinstance(info, dict) else getattr(info, "active_model", "default")
        )
        if target_model == "default" or not target_model:
            models = self._model_manager.list_models()
            target_model = models[0].get("id") if models else "local-model"

        # 2. 모델을 통해 명령어 번역
        try:
            from antigravity_k.engine.orchestrator import OrchestratorAgent

            orchestrator = OrchestratorAgent(model_manager=self._model_manager)
            messages = [{"role": "user", "content": prompt}]

            # Orchestrator.run_sync or a direct model generation
            command = orchestrator.run_sync(messages, target_model=target_model).strip()

            if command.startswith("```"):
                lines = command.split("\n")
                command = (
                    "\n".join(lines[1:-1])
                    if len(lines) > 2
                    else command.replace("```bash", "").replace("```sh", "").replace("```", "")
                )
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"❌ 명령어 번역 실패: {e}"

        # 3. 도구를 활용해 실행
        if not self._tool_registry or "run_bash_command" not in self._tool_registry._tools:
            return f"번역된 명령어: `{command}`\n\n(실행 실패: run_bash_command 도구를 찾을 수 없습니다.)"

        tool = self._tool_registry._tools["run_bash_command"]

        # 실제 환경에서는 사용자 확인을 거치거나 위험도 검사가 필요
        output = tool.execute(command=command, background=False)

        return (
            f"🤖 **AiShell 변환 완료**\n"
            f"> 원본: `{intent}`\n"
            f"> 명령: `{command}`\n\n"
            f"**실행 결과:**\n```text\n{output}\n```"
        )

    def _cmd_benchmark(self, args: list) -> str:
        """벤치마크 실행/보고서 출력."""
        if not self._model_manager:
            return "❌ ModelManager가 필요합니다."

        from antigravity_k.engine.benchmark_harness import BenchmarkHarness

        harness = BenchmarkHarness(model_manager=self._model_manager)

        if not args:
            return (
                "📊 **Benchmark 명령어**\n\n"
                "- `/benchmark run` — 전체 스위트 실행\n"
                "- `/benchmark run sim-001` — 특정 과제만 실행\n"
                "- `/benchmark run simple` — 카테고리별 실행\n"
                "- `/benchmark report` — 누적 비교표 출력\n"
                "- `/benchmark clear` — 누적 결과 초기화"
            )

        sub = args[0].lower()

        if sub == "run":
            suite_name = args[1] if len(args) > 1 else "all"

            def _run_stream():
                yield "🚀 **벤치마크 실행 시작**\n\n"
                yield f"스위트: `{suite_name}`\n\n"
                yield "⏳ 과제를 순차 실행 중입니다. VRAM 경합 방지를 위해 하나씩 처리합니다...\n\n"

                try:
                    report = harness.run_suite(suite_name)
                    yield f"✅ **벤치마크 완료** ({report.duration_s:.1f}s, {len(report.results)}건)\n\n"
                    yield harness.comparison_table(suite_name)
                except Exception as e:
                    logger.exception("Unhandled exception")
                    yield f"❌ 벤치마크 실행 실패: {e}"

            return _run_stream()

        elif sub == "report":
            suite_name = args[1] if len(args) > 1 else "all"
            return harness.comparison_table(suite_name)

        elif sub == "clear":
            harness.clear_history()
            return "🗑️ 벤치마크 누적 결과가 초기화되었습니다."

        else:
            return f"❓ 알 수 없는 하위 명령: `{sub}`. `/benchmark` 로 도움말을 확인하세요."

    def _cmd_dialectic(self, args: list) -> str:
        """변증법적 추론 실행 — Hegelion 패턴."""
        query = " ".join(args).strip()
        if not query:
            return (
                "⚖️ **변증법적 추론 엔진 (Hegelion)**\n\n"
                "Usage: `/dialectic <질문 또는 문제>`\n\n"
                "3단계 추론 (Thesis→Antithesis→Synthesis)으로\n"
                "문제를 다각도로 심층 분석합니다.\n\n"
                "Council 모드: `/dialectic council: <질문>` — "
                "Logician·Empiricist·Ethicist 3인 위원회 비판\n"
            )

        from antigravity_k.engine.dialectic_engine import DialecticEngine

        engine = DialecticEngine()

        # Council 모드 감지
        use_council = query.lower().startswith("council:")
        if use_council:
            query = query[len("council:") :].strip()

        prompt = engine.create_single_shot_prompt(query, use_council=use_council)

        # 모델이 있으면 실제 추론 실행
        if self._model_manager:
            try:
                from antigravity_k.engine.orchestrator import OrchestratorAgent

                orchestrator = OrchestratorAgent(model_manager=self._model_manager)
                messages = [{"role": "user", "content": prompt}]
                info = self._model_manager.get_model_info()
                target = (
                    info.get("active_model", "default")
                    if isinstance(info, dict)
                    else getattr(info, "active_model", "default")
                )
                raw_result = orchestrator.run_sync(messages, target_model=target)
                result = engine.parse_structured_response(raw_result, query)
                return engine.render_markdown(result)
            except Exception as e:
                logger.error("Dialectic execution error: %s", e, exc_info=True)
                return f"⚠️ 변증법 추론 실행 오류: {e}\n\n아래 프롬프트를 직접 사용할 수 있습니다:\n\n```\n{prompt[:500]}...\n```"  # noqa: E501

        # 모델 없으면 프롬프트만 반환
        return (
            "⚖️ **변증법적 추론 프롬프트 생성 완료**\n\n"
            "로컬 모델이 연결되지 않아 프롬프트만 생성합니다.\n"
            "아래 프롬프트를 LLM에 직접 전달하세요:\n\n"
            f"```\n{prompt}\n```"
        )

    def _cmd_finance(self, args: list) -> str:
        """금융 어시스턴트 커맨드 라우터 (/finance, /comps, /dcf)."""
        # 이 커맨드는 내부적으로 financial-assistant 페르소나 또는 fa-modeling 스킬을
        # 주입하기 위한 가이드 메시지를 출력하고 런타임에 컨텍스트를 주입하는 역할을 합니다.
        query = " ".join(args).strip()

        return (
            "💼 **Financial Assistant 가동 준비 완료**\n\n"
            f"요청하신 분석 대상: `{query if query else '미지정'}`\n\n"
            "Antigravity-K 시스템이 **financial-assistant** 및 **fa-modeling** 스킬을 장착했습니다.\n"
            "이제 DCF(가치평가), Comps(비교분석), 3-Statement 모델링 등 전문 금융 분석 요청을 자유롭게 대화로 이어가세요!\n"  # noqa: E501
            '(예시: "해당 기업의 과거 3년 재무 데이터를 기반으로 DCF 모델을 작성해줘. Base/Bear/Bull 시나리오를 적용해.")'  # noqa: E501
        )

    def _cmd_lifecycle(self, command_name: str, args: list) -> str:
        """Lifecycle command handler (e.g. /spec, /build)."""
        prompt = " ".join(args).strip()

        # Mapping to Addy Osmani's agent skills
        skill_maps = {
            "spec": "spec-driven-development",
            "plan": "planning-and-task-breakdown",
            "build": "incremental-implementation",
            "test": "test-driven-development",
            "review": "code-review-and-quality",
            "code-simplify": "code-simplification",
            "ship": "shipping-and-launch",
        }

        skill_name = skill_maps.get(command_name, command_name)

        if self._skill_loader:
            try:
                self._skill_loader.activate(skill_name)
            except Exception:
                logger.exception("Could not explicitly activate skill %s", skill_name)

        system_injection = (
            f"ACTIVATE LIFECYCLE SKILL: {skill_name}.\n"
            f"Please strictly follow the workflow and verification gates defined for this skill.\n"
            f"Task: {prompt}"
        )

        return self._execute_natural_language(system_injection)
