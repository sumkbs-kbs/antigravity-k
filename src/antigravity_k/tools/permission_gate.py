"""
PermissionGate — 3-Tier 권한 모델
==================================
Claw Code의 PermissionPolicy 아키텍처를 이식.

- Allow : 읽기 전용 도구 → 자동 실행
- Prompt: 파일 쓰기/수정 → 사용자 확인 후 실행
- Deny  : 시스템 변경/위험 명령 → 차단

사용:
    gate = PermissionGate(project_root="/path/to/project")
    decision = gate.check(tool, args)
    if decision == Permission.ALLOW: ...
"""
import os
import re
import logging
from enum import Enum
from typing import Dict, Any, Optional, List, Set

logger = logging.getLogger(__name__)


class Permission(str, Enum):
    """권한 결정 결과."""
    ALLOW = "allow"      # 자동 실행
    PROMPT = "prompt"    # 사용자 확인 필요
    DENY = "deny"        # 차단


class PermissionGate:
    """
    도구 실행 전 권한 검증 게이트.
    
    Claw Code의 PermissionPolicy struct 패턴:
    - per-tool 오버라이드
    - 경로 기반 샌드박싱
    - 위험 명령 블랙리스트
    """
    
    # ─── 위험 명령 블랙리스트 ───
    DANGEROUS_COMMANDS: List[str] = [
        r"rm\s+-rf\s+/",           # 루트 삭제
        r"del\s+/[sS]",            # Windows 전체 삭제
        r"format\s+[A-Za-z]:",     # 디스크 포맷
        r"mkfs\.",                  # 파일시스템 포맷
        r"dd\s+if=.*of=/dev/",     # 디스크 덮어쓰기
        r"chmod\s+-R\s+777\s+/",   # 전체 권한 오픈
        r"shutdown",               # 시스템 종료
        r"reboot",                 # 시스템 재시작
        r"curl.*\|\s*(ba)?sh",     # 원격 스크립트 실행
        r"wget.*\|\s*(ba)?sh",     # 원격 스크립트 실행
    ]
    
    # ─── 보호 경로 (절대 쓰기 불가) ───
    PROTECTED_PATHS: List[str] = [
        "/etc", "/usr", "/bin", "/sbin", "/boot", "/sys", "/proc",
        "C:\\Windows", "C:\\Program Files", "C:\\Program Files (x86)",
    ]
    
    def __init__(
        self,
        project_root: Optional[str] = None,
        mode: str = "auto-pilot",  # strict | balanced | permissive | auto-pilot
        auto_allow_safe: bool = True,
    ):
        self.project_root = os.path.abspath(project_root) if project_root else os.getcwd()
        self.mode = mode
        self.auto_allow_safe = auto_allow_safe
        
        # 도구별 명시적 오버라이드
        self._overrides: Dict[str, Permission] = {}
        
        # 승인 캐시 (세션 내 반복 승인 방지)
        self._approval_cache: Set[str] = set()
        
        logger.info(
            f"PermissionGate initialized: mode={mode}, "
            f"project_root={self.project_root}"
        )
    
    def set_project_root(self, new_root: str):
        """런타임 중에 프로젝트 루트를 변경하고 권한 모드를 자동화 모드로 설정합니다."""
        self.project_root = os.path.abspath(new_root)
        self.mode = "auto-pilot"  # 사용자의 개입 최소화를 위해 내부 파일 작업 자동 승인
        logger.info(f"PermissionGate project_root updated to: {self.project_root} (mode set to auto-pilot)")
    
    def set_override(self, tool_name: str, permission: Permission):
        """특정 도구에 대한 권한을 명시적으로 설정합니다."""
        self._overrides[tool_name] = permission
        logger.info(f"Permission override set: {tool_name} → {permission.value}")
    
    def check(self, tool_name: str, args: Dict[str, Any], risk_level: str = "safe") -> Permission:
        """
        도구 실행 권한을 검증합니다.
        
        Returns:
            Permission.ALLOW  — 즉시 실행
            Permission.PROMPT — 사용자 확인 필요
            Permission.DENY   — 차단
        """
        # 1. 명시적 오버라이드 우선
        if tool_name in self._overrides:
            return self._overrides[tool_name]
        
        # 2. 위험 명령 차단 (Bash/Shell 도구)
        if tool_name in ("run_bash_command", "bash"):
            command = args.get("command", "")
            if self._is_dangerous_command(command):
                logger.warning(f"DENIED dangerous command: {command[:100]}")
                return Permission.DENY
        
        # 3. 경로 기반 샌드박싱 (파일 쓰기 도구)
        path_decision = None
        file_path = args.get("file_path") or args.get("path") or args.get("target")
        if file_path:
            path_decision = self._check_path(file_path, tool_name)
            if path_decision == Permission.DENY:
                return Permission.DENY
        
        # 4. risk_level 기반 결정
        risk_map = {
            "safe": Permission.ALLOW,
            "low": Permission.ALLOW if self.mode in ("permissive", "auto-pilot") else Permission.PROMPT,
            "medium": Permission.ALLOW if self.mode == "auto-pilot" else Permission.PROMPT,
            "high": Permission.ALLOW if self.mode == "auto-pilot" else Permission.PROMPT,
            "critical": Permission.DENY if self.mode in ("strict", "balanced") else Permission.PROMPT,
        }
        
        decision = risk_map.get(risk_level, Permission.PROMPT)
        
        # 경로 검사에서 PROMPT가 요구되었다면, risk_map이 ALLOW더라도 PROMPT로 격상
        if path_decision == Permission.PROMPT and decision == Permission.ALLOW:
            decision = Permission.PROMPT
            
        # 5. 승인 캐시 확인 (같은 도구+패턴 반복 시 자동 승인)
        cache_key = f"{tool_name}:{risk_level}"
        if decision == Permission.PROMPT and cache_key in self._approval_cache:
            logger.debug(f"Auto-approved from cache: {cache_key}")
            return Permission.ALLOW
        
        return decision
    
    def record_approval(self, tool_name: str, risk_level: str = "safe"):
        """사용자가 승인한 도구를 캐시에 기록합니다."""
        cache_key = f"{tool_name}:{risk_level}"
        self._approval_cache.add(cache_key)
    
    def _is_dangerous_command(self, command: str) -> bool:
        """위험 명령 블랙리스트 검사."""
        for pattern in self.DANGEROUS_COMMANDS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False
    
    def _check_path(self, file_path: str, tool_name: str) -> Permission:
        """경로 기반 권한 검사."""
        abs_path = os.path.abspath(file_path)
        
        # 보호 경로 차단
        for protected in self.PROTECTED_PATHS:
            if abs_path.lower().startswith(protected.lower()):
                logger.warning(f"DENIED access to protected path: {abs_path}")
                return Permission.DENY
        
        # 프로젝트 외부 파일 접근 = Prompt
        # P1 수정: Windows 대소문자 불일치 방지 — normcase 적용
        if not os.path.normcase(abs_path).startswith(os.path.normcase(self.project_root)):
            if self.mode == "strict":
                return Permission.DENY
            return Permission.PROMPT
        
        # 프로젝트 내부 읽기 전용 = Allow
        if tool_name in ("read_file", "grep_search", "glob_search"):
            return Permission.ALLOW
        
        # 프로젝트 내부 쓰기 = 모드에 따라
        if self.mode == "permissive":
            return Permission.ALLOW
        return Permission.PROMPT
    
    def reset_cache(self):
        """승인 캐시를 초기화합니다."""
        self._approval_cache.clear()
    
    def to_dict(self) -> Dict[str, Any]:
        """상태를 직렬화합니다."""
        return {
            "project_root": self.project_root,
            "mode": self.mode,
            "overrides": {k: v.value for k, v in self._overrides.items()},
            "cached_approvals": list(self._approval_cache),
        }
