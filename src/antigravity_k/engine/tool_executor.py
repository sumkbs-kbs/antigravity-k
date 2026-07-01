"""Antigravity-K: 도구 실행 엔진 (ToolExecutor).

=============================================
I-1 리팩터링: Orchestrator에서 분리된 도구 실행/등록 로직.
도구 스키마 검증, 권한 검사, 에러 복구(Immune System), 자동 롤백을 담당합니다.
"""

import asyncio
import json
import logging
import os
from typing import Any

from antigravity_k.engine.immune_system import ImmuneSystem
from antigravity_k.tools.permission_gate import Permission, PermissionGate
from antigravity_k.tools.tool_registry import ToolRegistry

logger = logging.getLogger(__name__)


class ToolExecutor:
    """도구 실행 책임을 Orchestrator에서 분리한 모듈.

    책임:
    - 도구 스키마 사전 검증
    - PermissionGate 기반 권한 검사
    - 연속 에러 추적 및 자동 복구 (Immune System / Vault Rollback)
    - 도구 자동 등록 (_register_claw_tools)
    """

    def __init__(
        self,
        tool_registry: ToolRegistry,
        permission_gate: PermissionGate,
        model_manager=None,
        vault_engine=None,
        project_root: str = ".",
        capability_policy_config: dict[str, Any] | None = None,
    ):
        """Initialize the ToolExecutor.

        Args:
            tool_registry (ToolRegistry): ToolRegistry tool registry.
            permission_gate (PermissionGate): PermissionGate permission gate.
            model_manager: model manager.
            vault_engine: vault engine.
            project_root (str): str project root.
            capability_policy_config (dict[str, Any] | None): dict[str, Any] | None capability policy config.

        """
        self.tool_registry = tool_registry
        self.permission_gate = permission_gate
        self.manager = model_manager
        self.vault_engine = vault_engine
        self.project_root = project_root
        self.capability_policy_config = capability_policy_config or {}
        self._consecutive_errors = 0
        self.current_objective = ""

        # Singleton instantiation to avoid lazy init costs during active error recovery
        try:
            self._immune_system = ImmuneSystem(self.project_root, self.manager, self.vault_engine)
        except Exception:
            logger.exception("Failed to initialize ImmuneSystem in ToolExecutor")
            self._immune_system = None

    def set_objective(self, objective: str) -> None:
        """현재 턴 목표를 capability policy 판단에 제공합니다."""
        self.current_objective = objective or ""

    def execute(self, name: str, args: dict[str, Any], objective: str = "") -> str:
        """ToolRegistry를 통해 도구를 실행합니다. (사전 검증 및 구조화된 에러 반환 포함)."""
        try:
            if name not in self.tool_registry:
                self._consecutive_errors += 1
                return (
                    f"There was an error when executing the function: {name}\n"
                    f"Here's the error traceback: Unknown tool '{name}'\n"
                    f"Please call this function again with a valid tool name within XML tags <tool_call></tool_call>"
                )

            # ─── Pre-Execution Validation (스키마 사전 검증) ───
            tool_obj = self.tool_registry.get(name)
            if tool_obj:
                try:
                    schema = tool_obj.parameters_schema
                    required_args = schema.get("required", [])
                    missing = [arg for arg in required_args if arg not in args]
                    if missing:
                        self._consecutive_errors += 1
                        return (
                            f"There was an error when executing the function: {name}\n"
                            f"Here's the error traceback: Missing required arguments: {', '.join(missing)}\n"
                            f"Please call this function again with correct arguments within XML tags"
                            f"<tool_call></tool_call>"
                        )
                except Exception:
                    logger.exception("Validation check failed for %s", name)

            # ─── Preflight Validator (Hermes 차용) ───
            # 파일 읽기, 편집 도구 실행 전 경로가 존재하는지 확인하고,
            # 파일 쓰기 도구의 경우 대상 디렉토리가 없으면 자율적으로 생성합니다.
            file_path = args.get("file_path") or args.get("path") or args.get("target")
            if file_path:
                abs_path = file_path if os.path.isabs(file_path) else os.path.join(self.project_root, file_path)
                if name in (
                    "write_file",
                    "write_to_file",
                    "edit_file",
                    "replace_file_content",
                ):
                    parent_dir = os.path.dirname(abs_path)
                    if parent_dir and not os.path.exists(parent_dir):
                        try:
                            os.makedirs(parent_dir, exist_ok=True)
                            logger.info(
                                "Preflight Validator: Auto-created missing directory %s",
                                parent_dir,
                            )
                        except Exception:
                            logger.exception(
                                "Preflight Validator failed to create dir %s",
                                parent_dir,
                            )

            perm, result = self.tool_registry.execute_with_permission(
                name,
                args,
                objective=objective or self.current_objective,
            )

            if perm == Permission.DENY:
                self._consecutive_errors += 1
                return (
                    f"There was an error when executing the function: {name}\n"
                    f"Here's the error traceback: [DENIED] Tool execution blocked by permission rules.\n"
                    f"Please reconsider your approach."
                )
            elif perm == Permission.PROMPT:
                return (
                    f"[APPROVAL REQUIRED] This tool ({name}) requires user approval to execute. "
                    f"Please stop executing tools immediately and ask the user for permission. "
                    f"Wait for their 'Yes' before retrying."
                )

            if isinstance(result, str) and result.strip().startswith("Error"):
                self._consecutive_errors += 1
            else:
                self._consecutive_errors = 0  # Reset on success

                # Broadcast FileOpened / FileModified events to dashboard
                if name in (
                    "read_file",
                    "write_file",
                    "edit_file",
                    "replace_file_content",
                    "multi_replace_file_content",
                ):
                    file_path = args.get("file_path") or args.get("path")
                    if file_path:
                        abs_path = file_path if os.path.isabs(file_path) else os.path.join(self.project_root, file_path)
                        if os.path.exists(abs_path):
                            try:
                                with open(abs_path, encoding="utf-8") as f:
                                    content = f.read()
                                from antigravity_k.engine.event_bus import (
                                    global_event_bus,
                                )

                                evt_type = "FileOpened" if name == "read_file" else "FileModified"
                                global_event_bus.publish(
                                    evt_type,
                                    filepath=abs_path,
                                    content=content,
                                )
                            except Exception:
                                logger.exception("Failed to read file for event broadcast")

            # Auto-Rollback & Self-Healing logic
            if self._consecutive_errors >= 3:
                return self._trigger_recovery(name, args, result)

            return result
        except Exception as e:
            logger.exception("Unhandled exception")
            self._consecutive_errors += 1
            return (
                f"There was an error when executing the function: {name}\n"
                f"Here's the error traceback: {str(e)}\n"
                f"Please call this function again with correct arguments within XML tags <tool_call></tool_call>"
            )

    async def execute_async(self, name: str, args: dict[str, Any]) -> str:
        """비동기 스레드 풀에서 도구를 실행하여 메인 이벤트 루프를 블로킹하지 않습니다."""
        return await asyncio.to_thread(self.execute, name, args)

    def _trigger_recovery(self, name: str, args: dict[str, Any], result) -> str:
        """연속 에러 3회 시 Immune System → Vault Rollback 순으로 복구 시도."""
        self._consecutive_errors = 0

        # 1. Trigger Immune System (Self-Healing)
        if self._immune_system:
            try:
                error_trace = str(result)
                args_context = json.dumps(args, ensure_ascii=False) if args else "None"
                heal_msg = self._immune_system.heal(error_trace, name, args_context)
                return heal_msg
            except Exception:
                logger.exception("Immune System recovery failed")

        # 2. Fallback to Vault Rollback if Immune System fails
        rollback_msg = "\n\n🚨 **[SANDBOX RECOVERY]** Consecutive tool errors detected! "
        if self.vault_engine:
            try:
                snapshot = self.vault_engine.create_snapshot(
                    "Auto-rollback checkpoint before recovery",
                )
                if snapshot:
                    success = self.vault_engine.restore_snapshot(snapshot)
                    if success:
                        rollback_msg += (
                            f"Workspace has been safely rolled back to checkpoint ({snapshot[:7]}). "
                            f"Please analyze why the error occurred and formulate a completely different plan."
                        )
                    else:
                        rollback_msg += "Restore attempted but failed."
                else:
                    rollback_msg += "No recent snapshot found to rollback to."
            except Exception as ge:
                logger.exception("Unhandled exception")
                rollback_msg += f"Vault rollback failed: {ge}."
        else:
            rollback_msg += "VaultEngine is not available, so automatic rollback could not be performed."
        return str(result) + rollback_msg

    def register_default_tools(self):
        """모든 기본 도구를 ToolRegistry에 등록합니다."""
        try:
            from antigravity_k.tools.agent_spawn import AgentSpawnTool
            from antigravity_k.tools.artifact_tools import WriteArtifactTool
            from antigravity_k.tools.binary_tools import HexDumpTool
            from antigravity_k.tools.browser_tools import BrowserDOMTool
            from antigravity_k.tools.ci_tools import (
                AutoLintTool,
                PRCreationTool,
                TestRunnerTool,
            )
            from antigravity_k.tools.computer_use import ComputerUseTool
            from antigravity_k.tools.config_editor_tool import ConfigEditorTool
            from antigravity_k.tools.cowork_delegate import CoworkDelegateTool
            from antigravity_k.tools.docker_tools import DockerBashCommandTool
            from antigravity_k.tools.file_tools import (
                EditFileTool,
                GlobSearchTool,
                GrepSearchTool,
                WriteFileTool,
            )
            from antigravity_k.tools.git_tools import (
                GitCommitTool,
                GitDiffTool,
                GitLogTool,
                GitStatusTool,
            )
            from antigravity_k.tools.hashline_tools import (
                HashlineEditTool,
                MultiReplaceFileContentTool,
                ReadHashFileTool,
            )
            from antigravity_k.tools.impact_analyzer import ImpactAnalyzerTool
            from antigravity_k.tools.self_evolution_tool import SelfEvolutionTool
            from antigravity_k.tools.system_control import SystemControlTool
            from antigravity_k.tools.system_tools import (
                ListDirectoryTool,
                ReadFileTool,
                ReplaceFileContentTool,
                RunBashCommandTool,
            )
            from antigravity_k.tools.terminal_tools import InteractivePTYTool
            from antigravity_k.tools.web_search import WebSearchTool

            self.tool_registry.install_many(
                ComputerUseTool(),
                SystemControlTool(),
                InteractivePTYTool(),
                HexDumpTool(),
                DockerBashCommandTool(),
                ReadFileTool(),
                ReplaceFileContentTool(),
                MultiReplaceFileContentTool(),
                RunBashCommandTool(),
                WriteFileTool(),
                EditFileTool(),
                GlobSearchTool(),
                GrepSearchTool(),
                ListDirectoryTool(),
                ReadHashFileTool(),
                HashlineEditTool(),
                GitStatusTool(),
                GitDiffTool(),
                GitCommitTool(),
                GitLogTool(),
                TestRunnerTool(),
                AutoLintTool(),
                PRCreationTool(),
                ImpactAnalyzerTool(),
                ConfigEditorTool(),
                AgentSpawnTool(model_manager=self.manager, tool_registry=self.tool_registry),
                CoworkDelegateTool(model_manager=self.manager),
                SelfEvolutionTool(),
                WriteArtifactTool(),
                BrowserDOMTool(),
                WebSearchTool(),
            )
            logger.info("Registered %s tools via ToolRegistry", len(self.tool_registry))

            # MCP 동적 도구 로딩: 감사 통과한 서버만 ToolRegistry에 편입합니다.
            self._load_mcp_tools()

            # Auto-Skill 동적 로딩 (ECA)
            self._load_auto_skills()

        except Exception:
            logger.exception("Failed to register tools")

    def _load_auto_skills(self):
        """auto_skill_ 프리픽스 도구를 동적으로 로드합니다."""
        tools_dir = os.path.join(self.project_root, "src", "antigravity_k", "tools")
        if not os.path.exists(tools_dir):
            return

        import importlib.util
        import inspect

        from antigravity_k.tools.base_tool import BaseTool

        auto_skills = [f for f in os.listdir(tools_dir) if f.startswith("auto_skill_") and f.endswith(".py")]
        for skill_file in auto_skills:
            try:
                module_name = skill_file[:-3]
                spec = importlib.util.spec_from_file_location(
                    module_name,
                    os.path.join(tools_dir, skill_file),
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseTool) and obj is not BaseTool:
                        self.tool_registry.install(obj())
                        logger.info("Dynamically loaded auto-skill: %s from %s", name, skill_file)
            except Exception:
                logger.exception("Failed to load auto-skill %s", skill_file)

    def _load_mcp_tools(self):
        """프로젝트 MCP 설정을 감사한 뒤 안전한 MCP 도구를 동적으로 등록합니다."""
        config_path = os.environ.get("AGK_MCP_CONFIG") or os.path.join(
            self.project_root,
            ".mcp.json",
        )
        if self.capability_policy_config.get("auto_load_mcp", True) is False:
            logger.info("MCP auto-load disabled by autonomous_capabilities config.")
            return
        if not os.path.exists(config_path):
            return

        try:
            from antigravity_k.tools.mcp_tool_loader import MCPToolLoader

            loader = MCPToolLoader(
                config_path=config_path,
                include_system_tools=False,
            )
            for tool in loader.load_tools():
                if tool.name in self.tool_registry:
                    logger.warning(
                        "Skipping MCP tool '%s' because a local tool already exists.",
                        tool.name,
                    )
                    continue
                self.tool_registry.install(tool)
            logger.info("Registered MCP tools from %s", config_path)
        except Exception:
            logger.exception("Failed to load MCP tools from %s", config_path)

    def reset_error_counter(self):
        """턴 시작 시 에러 카운터를 리셋합니다."""
        self._consecutive_errors = 0
