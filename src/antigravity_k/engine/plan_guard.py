"""PlanGuard Engine (OpenHuman Pattern).

=====================================

파괴적인 명령어(rm -rf, DROP TABLE 등)나 대규모 아키텍처 변경을 감지하고,
실행 전 사용자의 상호작용적 승인(Human-In-The-Loop)을 요구하는 안전망 모듈입니다.
"""

import logging
import re
from dataclasses import dataclass
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class GuardDecision:
    """Guarddecision."""

    allows_execution: bool
    requires_approval: bool
    message: str
    risk_level: str


class PlanGuard:
    """명령어/도구 인자를 분석하여 위험도를 평가하고.

    자동 차단 또는 인간 개입(HITL)을 요청합니다.
    """

    # 파괴적 명령어 패턴 정의 (OpenHuman/Careful Guardrails 기반)
    DESTRUCTIVE_PATTERNS = [
        r"rm\s+-r[fF]?",  # 디렉토리 강제 삭제
        r"drop\s+(table|database)",  # SQL Drop
        r"git\s+reset\s+--hard",  # Git 하드 리셋
        r"git\s+push\s+.*--force",  # Git 강제 푸시
        r"kubectl\s+delete",  # k8s 리소스 삭제
        r"truncate\s+table",  # SQL Truncate
        r">\s*/dev/sda",  # 디스크 덮어쓰기 (극단적 예시)
        r"chmod\s+-R\s+777",  # 무차별 권한 변경
    ]

    def __init__(self, strict_mode: bool = False):
        """Initialize the PlanGuard.

        Args:
            strict_mode (bool): bool strict mode.

        """
        self.strict_mode = strict_mode
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.DESTRUCTIVE_PATTERNS]

    def evaluate_tool_call(self, tool_name: str, tool_args: dict[str, Any]) -> GuardDecision:
        """도구 호출의 위험도를 평가합니다."""
        # 1. 터미널/쉘 명령어 분석
        if tool_name in (
            "run_bash_command",
            "run_command",
            "docker_bash_command",
            "interactive_pty",
        ):
            cmd = tool_args.get("command", "") or tool_args.get("CommandLine", "")
            if self._is_destructive_command(cmd):
                return GuardDecision(
                    allows_execution=False,
                    requires_approval=True,
                    message=f"Destructive command detected: `{cmd}`. Execution blocked pending user approval.",
                    risk_level="HIGH",
                )

        # 2. 파일 덮어쓰기 분석 (전체 내용 대체)
        if tool_name in ("write_file", "write_to_file"):
            overwrite = tool_args.get("overwrite") or tool_args.get("Overwrite")
            if overwrite:
                target = tool_args.get("file_path") or tool_args.get("TargetFile") or "unknown"
                return GuardDecision(
                    allows_execution=False,
                    requires_approval=True,
                    message=f"Attempting to overwrite entire file: `{target}`. User approval required.",
                    risk_level="MEDIUM",
                )

        return GuardDecision(
            allows_execution=True,
            requires_approval=False,
            message="Safe to execute",
            risk_level="LOW",
        )

    def _is_destructive_command(self, cmd: str) -> bool:
        if not cmd:
            return False
        for pattern in self._compiled_patterns:
            if pattern.search(cmd):
                return True
        return False
