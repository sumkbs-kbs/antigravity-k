"""System Tools module."""

import logging
import os
import subprocess
from typing import Any

from .base_tool import BaseTool, RenderIn, RiskLevel, ToolCategory

logger = logging.getLogger(__name__)


class ReadFileTool(BaseTool):
    """Readfiletool.

    Bases: BaseTool
    """

    category = ToolCategory.FILE_IO
    render_in = RenderIn.TOOLBAR
    risk_level = RiskLevel.SAFE
    icon = "📄"
    tags = ["file", "read", "io", "view"]

    def __init__(self):
        """Initialize the ReadFileTool."""
        super().__init__()
        self._name = "read_file"
        self._description = (
            "Reads the content of a file. Supports optional line range selection "
            "with start_line and end_line for efficient partial reading of large files."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Absolute or relative path to the file.",
                },
                "start_line": {
                    "type": "integer",
                    "description": "Start line (1-indexed). Omit to read from beginning.",
                },
                "end_line": {
                    "type": "integer",
                    "description": "End line (1-indexed, inclusive). Omit to read to end.",
                },
            },
            "required": ["file_path"],
        }

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        file_path = kwargs.get("file_path")
        start_line = kwargs.get("start_line")
        end_line = kwargs.get("end_line")

        if not file_path or not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"
        try:
            with open(file_path, encoding="utf-8") as f:
                if start_line or end_line:
                    lines = f.readlines()
                    total = len(lines)
                    s = max(1, start_line or 1) - 1
                    e = min(total, end_line or total)
                    selected = lines[s:e]
                    # 줄 번호 포함 출력
                    numbered = [f"{i + s + 1}: {line}" for i, line in enumerate(selected)]
                    header = f"[Showing lines {s + 1}-{e} of {total} total]\n"
                    return header + "".join(numbered)
                else:
                    content = f.read()
                    # 800줄 초과 시 자동 truncate (컨텍스트 절약)
                    lines = content.split("\n")
                    if len(lines) > 800:
                        truncated = "\n".join(lines[:800])
                        return (
                            f"{truncated}\n\n[... truncated, {len(lines)} total lines. "
                            f"Use start_line/end_line for specific ranges.]"
                        )

                    return content
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"Error reading file: {e}"


class ReplaceFileContentTool(BaseTool):
    """Replacefilecontenttool.

    Bases: BaseTool
    """

    category = ToolCategory.FILE_IO
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.LOW
    icon = "✏️"
    tags = ["file", "write", "edit"]

    def __init__(self):
        """Initialize the ReplaceFileContentTool."""
        super().__init__()
        self._name = "replace_file_content"
        self._description = "Replaces a specific block of text in a file with new content."
        self._schema = {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Path to the file to modify.",
                },
                "target_text": {
                    "type": "string",
                    "description": "Exact text to be replaced.",
                },
                "replacement_text": {
                    "type": "string",
                    "description": "New text to replace the target text.",
                },
            },
            "required": ["file_path", "target_text", "replacement_text"],
        }

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        file_path = kwargs.get("file_path")
        target_text = kwargs.get("target_text", "")
        replacement_text = kwargs.get("replacement_text", "")

        if not file_path:
            return "Error: No file_path provided."
        if not os.path.exists(file_path):
            return f"Error: File not found at {file_path}"

        try:
            with open(file_path, encoding="utf-8") as f:
                content = f.read()

            if target_text not in content:
                return "Error: Target text not found in file."

            new_content = content.replace(target_text, replacement_text)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(new_content)

            return f"Successfully updated {file_path}."
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"Error replacing content: {e}"


class RunBashCommandTool(BaseTool):
    """Runbashcommandtool.

    Bases: BaseTool
    """

    category = ToolCategory.CODE_EXEC
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.HIGH
    icon = "⚡"
    tags = ["shell", "command", "bash", "exec"]

    def __init__(self):
        """Initialize the RunBashCommandTool."""
        super().__init__()
        self._name = "run_bash_command"
        self._description = (
            "Executes a shell command. Requires Human-In-The-Loop (HITL) approval unless Autopilot is enabled."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "command": {
                    "type": "string",
                    "description": "The shell command to execute.",
                },
            },
            "required": ["command"],
        }

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        command = kwargs.get("command")
        if not command:
            return "Error: No command provided."

        # [MAX AUTONOMY] 사용자 요청에 따라 모든 PC 자원(Bash 등)에 대해
        # HITL(Human-In-The-Loop) 제한을 해제하고 무조건 자율 판단으로 실행합니다.
        logger.info("[Auto-Pilot] Automatically executing command: %s", command)

        try:
            from ..engine.provider_manager import get_provider_manager

            pm = get_provider_manager()
            env_vars = os.environ.copy()
            env_vars.update(pm.get_provider_env())

            # P2-1: 샌드박스 적용 — config의 sandbox_enabled가 true면 OS 수준 격리
            sandbox_result = self._run_with_sandbox(command, env_vars)
            if sandbox_result is not None:
                return sandbox_result

            # 폴백: 일반 subprocess (샌드박스 비활성화 시)
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                env=env_vars,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            return output if output else "Command executed successfully with no output."
        except subprocess.TimeoutExpired:
            return "Error: Command timed out after 60 seconds."
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"Error executing command: {e}"

    def _run_with_sandbox(self, command: str, env_vars: dict) -> str | None:
        """샌드박스가 활성화된 경우 SandboxRunner로 실행 (P2-1).

        Returns:
            결과 문자열 (샌드박스 적용 시), None (비활성화 시 — 호출자가 폴백)
        """
        try:
            from ..config import config as app_config
            from ..engine.sandbox import SandboxRunner

            sandbox_enabled = getattr(app_config.security, "sandbox_enabled", False)
            if not sandbox_enabled:
                return None  # 샌드박스 비활성 — 폴백

            runner = SandboxRunner(
                project_root=str(app_config.paths.project_root),
                enabled=True,
                network=getattr(app_config.security, "sandbox_network", "none"),
                timeout=60,
            )
            result = runner.execute(command, env=env_vars)
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"
            if result.timed_out:
                return f"Error: {result.error}"
            tag = " [sandboxed]" if result.sandboxed else ""
            return (output if output else "Command executed successfully.") + tag
        except Exception:
            logger.debug("샌드박스 실행 실패 — raw subprocess로 폴백", exc_info=True)
            return None


class ListDirectoryTool(BaseTool):
    """디렉토리 탐색 도구.

    프로젝트 구조를 파악하기 위한 필수 도구.
    """

    category = ToolCategory.SEARCH
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.SAFE
    icon = "📂"
    tags = ["directory", "list", "explore", "tree"]

    def __init__(self):
        """Initialize the ListDirectoryTool."""
        super().__init__()
        self._name = "list_directory"
        self._description = (
            "Lists files and directories in a path. Shows file sizes and types. "
            "Excludes common non-essential directories like node_modules, .git, __pycache__."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": "Directory path to list.",
                    "default": ".",
                },
                "recursive": {
                    "type": "boolean",
                    "description": "List recursively (max 3 levels).",
                    "default": False,
                },
                "max_depth": {
                    "type": "integer",
                    "description": "Max recursion depth.",
                    "default": 3,
                },
            },
            "required": [],
        }

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        path = kwargs.get("path", ".")
        recursive = kwargs.get("recursive", False)
        max_depth = kwargs.get("max_depth", 3)

        IGNORE = {
            ".git",
            "node_modules",
            "__pycache__",
            ".venv",
            "venv",
            ".tox",
            "dist",
            "build",
            ".eggs",
            ".mypy_cache",
            ".pytest_cache",
            ".next",
        }

        if not os.path.isdir(path):
            return f"Error: '{path}' is not a directory."

        def _format_size(size):
            for unit in ["B", "KB", "MB", "GB"]:
                if size < 1024:
                    return f"{size:.0f}{unit}"
                size /= 1024
            return f"{size:.1f}TB"

        def _list(dir_path, depth=0):
            items = []
            try:
                entries = sorted(os.listdir(dir_path))
            except PermissionError:
                return [f"{'  ' * depth}[Permission denied]"]

            dirs, files = [], []
            for e in entries:
                if e in IGNORE or e.startswith("."):
                    continue
                full = os.path.join(dir_path, e)
                if os.path.isdir(full):
                    dirs.append(e)
                else:
                    files.append(e)

            for d in dirs:
                full = os.path.join(dir_path, d)
                child_count = (
                    len([x for x in os.listdir(full) if x not in IGNORE and not x.startswith(".")])
                    if os.path.isdir(full)
                    else 0
                )
                items.append(f"{'  ' * depth}📁 {d}/ ({child_count} items)")
                if recursive and depth < max_depth:
                    items.extend(_list(full, depth + 1))

            for f_name in files:
                full = os.path.join(dir_path, f_name)
                try:
                    size = _format_size(os.path.getsize(full))
                except OSError:
                    size = "?"
                items.append(f"{'  ' * depth}📄 {f_name} ({size})")

            return items

        lines = _list(path)
        if not lines:
            return f"Directory '{path}' is empty or contains only hidden/ignored files."

        header = f"Directory: {os.path.abspath(path)}\n{'=' * 40}\n"
        return header + "\n".join(lines[:200])  # 최대 200항목


class NaturalLanguageBashTool(BaseTool):
    """AiShell: Natural Language to Bash Command Tool.

    에이전트가 복잡한 bash 명령어의 문법을 고민하지 않고 자연어로 의도를 전달하면,
    LLM을 통해 정확한 쉘 명령어로 변환하여 실행합니다.
    """

    category = ToolCategory.SYSTEM
    render_in = RenderIn.CONTEXTUAL
    risk_level = RiskLevel.MEDIUM
    icon = "🤖"
    tags = ["bash", "shell", "nlp", "aishell"]

    def __init__(self):
        """Initialize the NaturalLanguageBashTool."""
        super().__init__()
        self._name = "aishell"
        self._description = (
            "Translate a natural language task into a macOS shell command and execute it. "
            "Use this when you want to run complex commands (awk, sed, ffmpeg, git) but are unsure of the exact syntax."
        )
        self._schema = {
            "type": "object",
            "properties": {
                "intent": {
                    "type": "string",
                    "description": "Natural language description of what you want to do (e.g. 'find all python files modified yesterday')",  # noqa: E501
                },
            },
            "required": ["intent"],
        }

    @property
    def name(self) -> str:
        """Name.

        Returns:
            str: The str result.

        """
        return self._name

    @property
    def description(self) -> str:
        """Description.

        Returns:
            str: The str result.

        """
        return self._description

    @property
    def parameters_schema(self) -> dict[str, Any]:
        """Parameters Schema.

        Returns:
            dict[str, Any]: The dict[str, any] result.

        """
        return self._schema

    def execute(self, **kwargs) -> Any:
        """Execute.

        Args:
            **kwargs: kwargs.

        Returns:
            Any: The any result.

        """
        intent = kwargs.get("intent")
        if not intent:
            return "Error: No intent provided."

        try:
            from ..engine.model_manager import ModelManager
            from ..engine.orchestrator import OrchestratorAgent

            prompt = "Translate the following task to a macOS shell command. Users provide a text-query as input.\nProvide ONLY the"  # type: ignore  # noqa: E501
            "command in ONE LINE, with no explanation:\n\nOne-line command for: {intent}"

            try:
                # Use default ModelManager and Orchestrator
                model_manager = ModelManager()
                orchestrator = OrchestratorAgent(model_manager=model_manager)

                try:
                    info = model_manager._registry.list_models()  # type: ignore[union-attr]
                    target_model = info[0].name if info else "qwen3.6:latest"
                except Exception:
                    target_model = "qwen3.6:latest"

                messages = [{"role": "user", "content": prompt}]
                command = orchestrator.run_sync(messages, target_model=target_model).strip()

                # Remove markdown code blocks if any
                if command.startswith("```"):
                    lines = command.split("\n")
                    command = (
                        "\n".join(lines[1:-1])
                        if len(lines) > 2
                        else command.replace("```bash", "").replace("```sh", "").replace("```", "")
                    )
            except Exception as e:
                logger.exception("Unhandled exception")
                return f"Error translating intent to bash via ModelManager: {e}"

            logger.info("AiShell translated '%s' -> `%s`", intent, command)

            import os

            from ..engine.provider_manager import get_provider_manager

            # Now execute it
            pm = get_provider_manager()
            env_vars = os.environ.copy()
            env_vars.update(pm.get_provider_env())

            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=60,
                env=env_vars,
            )
            output = result.stdout
            if result.stderr:
                output += f"\nSTDERR:\n{result.stderr}"

            return f"Executed Command: `{command}`\n\nOutput:\n{output if output else 'Success (no output).'}"

        except Exception as e:
            logger.exception("Unhandled exception")
            return f"AiShell execution failed: {e}"
