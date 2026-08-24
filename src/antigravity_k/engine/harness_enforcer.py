"""Harness Enforcer module."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, ClassVar


@dataclass(frozen=True)
class HarnessFeedbackAction:
    """Harnessfeedbackaction."""

    action_type: str = "continue"
    reason: str = ""


def load_longrun_harness_prompt(project_root: str = ".") -> str:
    """장기 자율 실행 하네스 프롬프트(prompts/harness_longrun_v1.md)를 로드한다.

    파일이 없거나 읽지 못하면 빈 문자열 — 호출자는 빈 값일 때 주입을 생략한다.
    """
    path = Path(project_root) / "prompts" / "harness_longrun_v1.md"
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError:
        return ""


class HarnessEnforcer:
    """Small runtime boundary checker for tool calls inside the agent loop."""

    _BLOCKED_TOOLS: ClassVar[set[str]] = {"terminal_ws"}
    _DESTRUCTIVE_PATTERNS: ClassVar[tuple[re.Pattern[str], ...]] = (
        re.compile(r"\brm\s+-rf\s+/(?:\s|$)", re.IGNORECASE),
        re.compile(r"\b(format|mkfs|diskutil\s+erase|wipe)\b", re.IGNORECASE),
    )

    # AVO 스타일 스톨 감지: 동일 (tool, args-hash) 반복 임계. 2회째 시도는
    # 이미 반복이므로 차단하고 전략수정 프롬프트를 되돌려준다.
    STALL_REPEAT_THRESHOLD: ClassVar[int] = 2

    def __init__(self, project_root: str = ".", strict_mode: bool = False):
        """Initialize the HarnessEnforcer.

        Args:
            project_root (str): str project root.
            strict_mode (bool): bool strict mode.

        """
        self.project_root = str(Path(project_root).resolve())
        self.strict_mode = strict_mode
        self.guidelines: dict[str, Any] = {}
        self._call_counts: dict[str, int] = {}

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

    def reset_stall_tracking(self) -> None:
        """스톨 카운터를 초기화한다 (새 목표/세션 시작 시 호출)."""
        self._call_counts.clear()

    @staticmethod
    def build_stall_message(tool_name: str) -> str:
        """스톨 차단 시 모델에 되돌려줄 전략수정 지시문."""
        return (
            f"[STALL DETECTED] 동일 도구·동일 인자 {HarnessEnforcer.STALL_REPEAT_THRESHOLD}회 반복\n"
            f"[폐기] {tool_name} 동일 인자 재시도\n"
            "[대안 가설] 같은 방식의 재시도는 금지다. 원인 분류 후 구조적으로 다른 "
            "접근 1개를 가설로 세우고 즉시 실행하라."
        )

    def check_tool_boundary(
        self,
        tool_name: str,
        tool_args: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Check Tool Boundary.

        Args:
            tool_name (str): str tool name.
            tool_args (dict | None): dict | None tool args.

        Returns:
            dict: The dict result. 스톨 감지 시 allowed=False + STALL 지시문.

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

        if self._is_stalled(tool_name, args):
            return {
                "allowed": False,
                "reason": self.build_stall_message(tool_name),
                "stall": True,
            }

        return {"allowed": True, "reason": ""}

    def _is_stalled(self, tool_name: str, args: dict[str, Any]) -> bool:
        """동일 (tool, args) 호출 횟수 기반 스톨 판정. 허용 경로만 카운트된다."""
        try:
            payload = json.dumps(args, sort_keys=True, ensure_ascii=False, default=str)
        except (TypeError, ValueError):
            payload = repr(args)
        digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()[:12]
        key = f"{tool_name}:{digest}"
        count = self._call_counts.get(key, 0) + 1
        self._call_counts[key] = count
        return count >= self.STALL_REPEAT_THRESHOLD

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
