"""
Antigravity-K: 도구 실행 엔진 (ToolExecutor)
=============================================
I-1 리팩터링: Orchestrator에서 분리된 도구 실행/등록 로직.
도구 스키마 검증, 권한 검사, 에러 복구(Immune System), 자동 롤백을 담당합니다.
"""

import os
import json
import logging
import asyncio
from typing import Any, Dict

from antigravity_k.tools.tool_registry import ToolRegistry
from antigravity_k.tools.permission_gate import PermissionGate, Permission
from antigravity_k.engine.immune_system import ImmuneSystem

logger = logging.getLogger(__name__)


class ToolExecutor:
    """
    도구 실행 책임을 Orchestrator에서 분리한 모듈.

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
    ):
        self.tool_registry = tool_registry
        self.permission_gate = permission_gate
        self.manager = model_manager
        self.vault_engine = vault_engine
        self.project_root = project_root
        self._consecutive_errors = 0

        # Singleton instantiation to avoid lazy init costs during active error recovery
        try:
            self._immune_system = ImmuneSystem(
                self.project_root, self.manager, self.vault_engine
            )
        except Exception as e:
            logger.error(f"Failed to initialize ImmuneSystem in ToolExecutor: {e}")
            self._immune_system = None

    def execute(self, name: str, args: Dict[str, Any]) -> str:
        """ToolRegistry를 통해 도구를 실행합니다. (사전 검증 및 구조화된 에러 반환 포함)"""
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
                            f"Please call this function again with correct arguments within XML tags <tool_call></tool_call>"
                        )
                except Exception as ve:
                    logger.warning(f"Validation check failed for {name}: {ve}")

            perm, result = self.tool_registry.execute_with_permission(name, args)

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
                        abs_path = (
                            file_path
                            if os.path.isabs(file_path)
                            else os.path.join(self.project_root, file_path)
                        )
                        if os.path.exists(abs_path):
                            try:
                                with open(abs_path, "r", encoding="utf-8") as f:
                                    content = f.read()
                                from antigravity_k.engine.event_bus import (
                                    global_event_bus,
                                )

                                evt_type = (
                                    "FileOpened"
                                    if name == "read_file"
                                    else "FileModified"
                                )
                                global_event_bus.publish(
                                    evt_type, filepath=abs_path, content=content
                                )
                            except Exception as e:
                                logger.warning(
                                    f"Failed to read file for event broadcast: {e}"
                                )

            # Auto-Rollback & Self-Healing logic
            if self._consecutive_errors >= 3:
                return self._trigger_recovery(name, args, result)

            return result
        except Exception as e:
            self._consecutive_errors += 1
            return (
                f"There was an error when executing the function: {name}\n"
                f"Here's the error traceback: {str(e)}\n"
                f"Please call this function again with correct arguments within XML tags <tool_call></tool_call>"
            )

    async def execute_async(self, name: str, args: Dict[str, Any]) -> str:
        """비동기 스레드 풀에서 도구를 실행하여 메인 이벤트 루프를 블로킹하지 않습니다."""
        return await asyncio.to_thread(self.execute, name, args)

    def _trigger_recovery(self, name: str, args: Dict[str, Any], result) -> str:
        """연속 에러 3회 시 Immune System → Vault Rollback 순으로 복구 시도."""
        self._consecutive_errors = 0

        # 1. Trigger Immune System (Self-Healing)
        if self._immune_system:
            try:
                error_trace = str(result)
                args_context = json.dumps(args, ensure_ascii=False) if args else "None"
                heal_msg = self._immune_system.heal(error_trace, name, args_context)
                return heal_msg
            except Exception as ie:
                logger.error(f"Immune System recovery failed: {ie}")

        # 2. Fallback to Vault Rollback if Immune System fails
        rollback_msg = (
            "\n\n🚨 **[SANDBOX RECOVERY]** Consecutive tool errors detected! "
        )
        if self.vault_engine:
            try:
                snapshot = self.vault_engine.create_snapshot(
                    "Auto-rollback checkpoint before recovery"
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
                rollback_msg += f"Vault rollback failed: {ge}."
        else:
            rollback_msg += "VaultEngine is not available, so automatic rollback could not be performed."
        return str(result) + rollback_msg

    def register_default_tools(self):
        """모든 기본 도구를 ToolRegistry에 등록합니다."""
        try:
            from antigravity_k.tools.file_tools import (
                WriteFileTool,
                EditFileTool,
                GlobSearchTool,
                GrepSearchTool,
            )
            from antigravity_k.tools.git_tools import (
                GitStatusTool,
                GitDiffTool,
                GitCommitTool,
                GitLogTool,
            )
            from antigravity_k.tools.system_tools import (
                ReadFileTool,
                ReplaceFileContentTool,
                RunBashCommandTool,
                ListDirectoryTool,
            )
            from antigravity_k.tools.hashline_tools import (
                ReadHashFileTool,
                HashlineEditTool,
                MultiReplaceFileContentTool,
            )
            from antigravity_k.tools.agent_spawn import AgentSpawnTool
            from antigravity_k.tools.browser_tools import BrowserDOMTool
            from antigravity_k.tools.web_search import WebSearchTool
            from antigravity_k.tools.ci_tools import (
                TestRunnerTool,
                AutoLintTool,
                PRCreationTool,
            )
            from antigravity_k.tools.impact_analyzer import ImpactAnalyzerTool
            from antigravity_k.tools.artifact_tools import WriteArtifactTool
            from antigravity_k.tools.cowork_delegate import CoworkDelegateTool
            from antigravity_k.tools.self_evolution_tool import SelfEvolutionTool
            from antigravity_k.tools.config_editor_tool import ConfigEditorTool
            from antigravity_k.tools.docker_tools import DockerBashCommandTool
            from antigravity_k.tools.binary_tools import HexDumpTool
            from antigravity_k.tools.terminal_tools import InteractivePTYTool
            from antigravity_k.tools.computer_use import ComputerUseTool
            from antigravity_k.tools.system_control import SystemControlTool

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
                AgentSpawnTool(
                    model_manager=self.manager, tool_registry=self.tool_registry
                ),
                CoworkDelegateTool(model_manager=self.manager),
                SelfEvolutionTool(),
                WriteArtifactTool(),
                BrowserDOMTool(),
                WebSearchTool(),
            )
            logger.info(f"Registered {len(self.tool_registry)} tools via ToolRegistry")

            # Auto-Skill 동적 로딩 (ECA)
            self._load_auto_skills()

        except Exception as e:
            logger.warning(f"Failed to register tools: {e}")

    def _load_auto_skills(self):
        """auto_skill_ 프리픽스 도구를 동적으로 로드합니다."""
        tools_dir = os.path.join(self.project_root, "src", "antigravity_k", "tools")
        if not os.path.exists(tools_dir):
            return

        import importlib.util
        import inspect
        from antigravity_k.tools.base_tool import BaseTool

        auto_skills = [
            f
            for f in os.listdir(tools_dir)
            if f.startswith("auto_skill_") and f.endswith(".py")
        ]
        for skill_file in auto_skills:
            try:
                module_name = skill_file[:-3]
                spec = importlib.util.spec_from_file_location(
                    module_name, os.path.join(tools_dir, skill_file)
                )
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)

                for name, obj in inspect.getmembers(module, inspect.isclass):
                    if issubclass(obj, BaseTool) and obj is not BaseTool:
                        self.tool_registry.install(obj())
                        logger.info(
                            f"Dynamically loaded auto-skill: {name} from {skill_file}"
                        )
            except Exception as e:
                logger.warning(f"Failed to load auto-skill {skill_file}: {e}")

    def reset_error_counter(self):
        """턴 시작 시 에러 카운터를 리셋합니다."""
        self._consecutive_errors = 0
