"""
SlashCommands — 슬래시 커맨드 레지스트리
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
from typing import Any, Callable, Dict, List, Optional, Tuple

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
        self.name = name
        self.description = description
        self.handler = handler
        self.usage = usage or f"/{name}"
        self.category = category


class SlashCommandRegistry:
    """
    슬래시 커맨드 중앙 레지스트리.
    
    Claw Code의 CommandRegistry 패턴:
    - /help, /tools, /context, /memory, /model, /status, /compact, /session
    """
    
    def __init__(
        self,
        tool_registry=None,
        session_manager=None,
        context_shaper=None,
        model_manager=None,
    ):
        self._commands: Dict[str, SlashCommand] = {}
        self._tool_registry = tool_registry
        self._session_manager = session_manager
        self._context_shaper = context_shaper
        self._model_manager = model_manager
        
        # 기본 커맨드 등록
        self._register_defaults()
    
    def _register_defaults(self):
        """기본 슬래시 커맨드를 등록합니다."""
        
        self.register(SlashCommand(
            name="help",
            description="사용 가능한 슬래시 커맨드 목록을 표시합니다.",
            handler=self._cmd_help,
            usage="/help",
            category="general",
        ))
        
        self.register(SlashCommand(
            name="tools",
            description="등록된 도구 목록과 상태를 표시합니다.",
            handler=self._cmd_tools,
            usage="/tools [category]",
            category="tools",
        ))
        
        self.register(SlashCommand(
            name="context",
            description="현재 컨텍스트 토큰 사용량을 분석합니다.",
            handler=self._cmd_context,
            usage="/context",
            category="context",
        ))
        
        self.register(SlashCommand(
            name="memory",
            description="세션 Working Memory 내용을 조회합니다.",
            handler=self._cmd_memory,
            usage="/memory [key]",
            category="session",
        ))
        
        self.register(SlashCommand(
            name="model",
            description="현재 모델 정보를 확인하거나 변경합니다.",
            handler=self._cmd_model,
            usage="/model [model_name]",
            category="model",
        ))
        
        self.register(SlashCommand(
            name="status",
            description="에이전트 전체 상태를 요약합니다.",
            handler=self._cmd_status,
            usage="/status",
            category="general",
        ))
        
        self.register(SlashCommand(
            name="compact",
            description="수동으로 컨텍스트 압축을 트리거합니다.",
            handler=self._cmd_compact,
            usage="/compact",
            category="context",
        ))
        
        self.register(SlashCommand(
            name="session",
            description="세션 관리 (list/save/load/info).",
            handler=self._cmd_session,
            usage="/session [list|save|load <id>|info]",
            category="session",
        ))
        
        self.register(SlashCommand(
            name="project",
            description="새 프로젝트를 초기화하고 해당 폴더로 컨텍스트를 바인딩합니다.",
            handler=self._cmd_project,
            usage="/project <folder_path>",
            category="session",
        ))
        
        self.register(SlashCommand(
            name="approve",
            description="대기 중인 도구 실행을 승인합니다.",
            handler=self._cmd_approve,
            usage="/approve <tool_name>",
            category="system",
        ))
        
        self.register(SlashCommand(
            name="browse",
            description="특화된 서브 에이전트를 통해 웹 브라우저를 자율 탐색합니다.",
            handler=self._cmd_browse,
            usage="/browse <url> [지시사항]",
            category="system",
        ))
        
        self.register(SlashCommand(
            name="skill",
            description="특정 스킬(Markdown 지침서)을 에이전트 시스템 프롬프트에 주입하거나 관리합니다.",
            handler=self._cmd_skill,
            usage="/skill [list|activate <id>|deactivate <id>|clear]",
            category="system",
        ))
        
        self.register(SlashCommand(
            name="qa",
            description="DOM 파싱 도구를 사용해 대시보드 UI를 자가 점검합니다.",
            handler=self._cmd_qa,
            usage="/qa [url]",
            category="system",
        ))

        self.register(SlashCommand(
            name="aishell",
            description="자연어 지시를 파싱하여 터미널(Bash) 커맨드로 즉시 변환 후 실행합니다.",
            handler=self._cmd_aishell,
            usage="/aishell <명령어>",
            category="system",
        ))
    
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
        if not text.startswith("/"):
            return self._execute_natural_language(text)

        parts = text.strip().split()
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
            logger.error(f"Slash command error: {e}", exc_info=True)
            return f"Error executing /{cmd_name}: {e}"
            
    def _execute_natural_language(self, text: str) -> str:
        """슬래시가 없는 자연어를 받아서 로컬 모델을 통해 자율적으로 도구를 실행하고 답변을 반환합니다."""
        from antigravity_k.engine.orchestrator import OrchestratorAgent
        
        if not self._model_manager:
            return "Error: Model manager is not available for natural language execution."
            
        info = self._model_manager.get_model_info()
        target_model = info.get("active_model", "default") if isinstance(info, dict) else getattr(info, "active_model", "default")
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
            logger.error(f"Natural language execution error: {e}", exc_info=True)
            return f"자연어 처리 중 오류 발생: {e}"
    
    def get_completions(self, prefix: str) -> List[str]:
        """자동완성 후보를 반환합니다."""
        if not prefix.startswith("/"):
            return []
        search = prefix[1:]
        return [f"/{name}" for name in self._commands if name.startswith(search)]
    
    # ─────────── 기본 커맨드 핸들러 ───────────
    
    def _cmd_help(self, args: list) -> str:
        """도움말 표시."""
        lines = ["📚 **Antigravity-K 슬래시 커맨드**", ""]
        
        categories: Dict[str, List[SlashCommand]] = {}
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
            # 카테고리 필터
            tools = [t for t in tools if t.category.value == args[0]]
        
        for tool in tools:
            risk_icon = {"safe": "🟢", "low": "🟡", "medium": "🟠", "high": "🔴", "critical": "⛔"
            }.get(tool.risk_level.value, "⚪")
            lines.append(
                f"  {tool.icon} `{tool.name}` {risk_icon} — {tool.description[:60]}"
            )
        
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
        
        lines.extend([
            "",
            "  **압축 통계:**",
            f"    총 압축: {stats.get('total_shaped', 0)}회",
            f"    절약 토큰: {stats.get('tokens_saved', 0):,}",
            f"    콘텐츠 축소: {stats.get('collapses', 0)}건",
        ])
        
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
                return f"모델 변경 실패: {e}"
        
        # 현재 모델 정보
        try:
            info = self._model_manager.get_model_info()
            return f"🤖 **현재 모델:** {info}"
        except Exception:
            return "모델 정보를 가져올 수 없습니다."
    
    def _cmd_status(self, args: list) -> str:
        """전체 상태 요약."""
        lines = ["⚡ **Antigravity-K 상태**", ""]
        
        # 세션 정보
        if self._session_manager:
            info = self._session_manager.get_session_info()
            if info:
                lines.extend([
                    f"  **세션:** {info['id']}",
                    f"  **턴 수:** {info['turn_count']}",
                    f"  **메시지:** {info['message_count']}",
                    f"  **메모리 키:** {len(info['memory_keys'])}개",
                    "",
                ])
        
        # 도구 정보
        if self._tool_registry:
            lines.append(f"  **도구:** {len(self._tool_registry)}개 등록됨")
        
        # 컨텍스트 정보
        if self._context_shaper:
            stats = self._context_shaper.get_stats()
            lines.append(f"  **압축 횟수:** {stats.get('total_shaped', 0)}회")
        
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
                lines.append(
                    f"  `{s['id']}` — 턴: {s['turn_count']}, "
                    f"경로: {s['project_path']}"
                )
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
            "tracks.md": "# Tracks Registry\n\n진행 중인 트랙 목록.\n"
        }
        
        for fname, content in files_to_create.items():
            fpath = os.path.join(conductor_dir, fname)
            if not os.path.exists(fpath):
                try:
                    with open(fpath, "w", encoding="utf-8") as f:
                        f.write(content)
                except Exception as e:
                    logger.error(f"Failed to create scaffolding file {fpath}: {e}")
                    
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
            report.append(f"❌ **UI 에러 발생:** 화면 내에 다음 에러 키워드가 포함되어 있습니다: {', '.join(found_errors)}")
        else:
            report.append("✅ **UI 에러 없음:** 화면 내 치명적 에러 문구 미검출.")
            
        # 3. 모델 드롭다운 확인 (qwen, deepseek, llama 등)
        model_keywords = ["qwen", "deepseek", "llama", "phi"]
        found_models = [kw for kw in model_keywords if kw.lower() in result.lower()]
        if found_models:
            report.append(f"✅ **모델 로드 확인:** 드롭다운 내 다음 모델들이 발견됨: {', '.join(found_models)}")
        else:
            report.append("⚠️ **모델 미발견:** 화면에서 설치된 로컬 모델 목록을 찾을 수 없습니다.")
            
        report.append("\n**추출된 DOM 텍스트 요약 (최대 300자):**")
        report.append(f"```text\n{result[:300]}...\n```")
        
        return "\n".join(report)



    def _cmd_approve(self, args: list) -> str:
        return "System command: /approve is managed by the orchestrator."

    def _cmd_browse(self, args: list) -> str:
        return "System command: /browse is managed by the orchestrator."

    def _cmd_skill(self, args: list) -> str:
        return "System command: /skill is managed by the orchestrator."

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
        target_model = info.get("active_model", "default") if isinstance(info, dict) else getattr(info, "active_model", "default")
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
                command = "\n".join(lines[1:-1]) if len(lines) > 2 else command.replace("```bash", "").replace("```sh", "").replace("```", "")
        except Exception as e:
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
