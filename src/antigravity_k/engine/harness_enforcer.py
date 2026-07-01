"""Harness Enforcer module."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class HarnessFeedbackAction:
    """Harnessfeedbackaction."""

    action_type: str = "continue"
    reason: str = ""


class HarnessEnforcer:
    """Small runtime boundary checker for tool calls inside the agent loop."""

    _BLOCKED_TOOLS = {"terminal_ws"}
    _DESTRUCTIVE_PATTERNS = (
        re.compile(r"\brm\s+-rf\s+/(?:\s|$)", re.IGNORECASE),
        re.compile(r"\b(format|mkfs|diskutil\s+erase|wipe)\b", re.IGNORECASE),
    )

    def __init__(self, project_root: str = ".", strict_mode: bool = False):
        """Initialize the HarnessEnforcer.

        Args:
            project_root (str): str project root.
            strict_mode (bool): bool strict mode.

        """
        self.project_root = str(Path(project_root).resolve())
        self.strict_mode = strict_mode
        self.guidelines: dict[str, Any] = {}

    def load_guidelines(self) -> None:
        """Load optional harness guidance when present."""
        candidates = [
            Path(self.project_root) / "harness.json",
            Path(self.project_root) / ".agent" / "harness.json",
        ]
        for path in candidates:
            if not path.exists():
                continue
            try:
                self.guidelines = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                self.guidelines = {}
            return

    def check_tool_boundary(self, tool_name: str, tool_args: dict | None = None) -> dict:
        """Check Tool Boundary.

        Args:
            tool_name (str): str tool name.
            tool_args (dict | None): dict | None tool args.

        Returns:
            dict: The dict result.

        """
        args = tool_args or {}
        if tool_name in self._BLOCKED_TOOLS:
            return {"allowed": False, "reason": f"{tool_name} is not an agent tool"}

        command = str(args.get("command", ""))
        if any(pattern.search(command) for pattern in self._DESTRUCTIVE_PATTERNS):
            return {"allowed": False, "reason": "destructive shell command blocked"}

        path_value = args.get("path") or args.get("file_path") or args.get("target")
        if path_value and not self._path_allowed(str(path_value)):
            return {"allowed": False, "reason": "path is outside project boundary"}

        return {"allowed": True, "reason": ""}

    def feedback_loop(self, tool_result: str) -> HarnessFeedbackAction:
        """Feedback Loop.

        Args:
            tool_result (str): str tool result.

        Returns:
            HarnessFeedbackAction: The harnessfeedbackaction result.

        """
        lowered = (tool_result or "").lower()
        error_markers = ("traceback", "permission denied", "no such file", "error")
        if sum(marker in lowered for marker in error_markers) >= 2:
            return HarnessFeedbackAction("escalate", "repeated tool failure markers")
        return HarnessFeedbackAction()

    def _path_allowed(self, raw_path: str) -> bool:
        if not self.strict_mode:
            return True
        target = Path(raw_path)
        if not target.is_absolute():
            target = Path(self.project_root) / target
        try:
            os.path.commonpath([self.project_root, str(target.resolve())])
        except ValueError:
            return False
        return os.path.commonpath([self.project_root, str(target.resolve())]) == self.project_root
