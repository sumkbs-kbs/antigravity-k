"""Antigravity-K: 승인 관리자 (P1-3).

====================================
위험한 도구 실행 전 사용자 승인을 요청하는 인터랙티브 흐름.
Codex/Cursor 수준의 "신뢰할 수 있는 자율성"을 제공합니다.

핵심 기능:
  - 대기 중인 승인 요청 관리 (pending queue)
  - diff 미리보기 자동 생성 (파일 편집 도구)
  - 타임아웃 자동 거부 (안전 기본값)
  - "항상 허용" 옵션 (사용자 편의)
  - SSE 폴링 API 연동 지원

동작 흐름:
  1. ToolExecutor가 PROMPT 권한을 받음
  2. ApprovalManager.request_approval()로 대기 요청 생성
  3. API/SSE로 클라이언트에 알림
  4. 사용자가 수락/거부/항상허용 선택
  5. ToolExecutor가 결과를 받아 계속 진행 또는 중단
"""

from __future__ import annotations

import asyncio
import difflib
import logging
import os
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity_k.approval_manager")


class ApprovalStatus(str, Enum):
    """승인 상태."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    TIMEOUT = "timeout"
    ALWAYS_ALLOW = "always_allow"  # 이 도구는 향후 자동 승인


class ApprovalDecision(str, Enum):
    """사용자의 승인 결정."""

    APPROVE = "approve"
    DENY = "deny"
    ALWAYS_ALLOW = "always_allow"


@dataclass
class ApprovalRequest:
    """하나의 승인 요청."""

    request_id: str
    tool_name: str
    tool_args: dict[str, Any]
    risk_level: str = "medium"
    description: str = ""
    diff_preview: str = ""
    created_at: float = field(default_factory=time.time)
    status: ApprovalStatus = ApprovalStatus.PENDING
    resolved_at: float | None = None
    timeout_sec: int = 120

    @property
    def is_expired(self) -> bool:
        """타임아웃 만료 여부."""
        if self.status != ApprovalStatus.PENDING:
            return False
        return (time.time() - self.created_at) > self.timeout_sec

    def to_dict(self) -> dict:
        """API 응답용 dict."""
        return {
            "request_id": self.request_id,
            "tool_name": self.tool_name,
            "risk_level": self.risk_level,
            "description": self.description,
            "diff_preview": self.diff_preview,
            "status": self.status.value,
            "created_at": self.created_at,
            "timeout_sec": self.timeout_sec,
        }


class ApprovalManager:
    """승인 요청을 관리하는 싱글톤 매니저.

    사용법:
        manager = get_approval_manager()
        request = manager.request_approval(
            tool_name="edit_file",
            tool_args={"file_path": "app.py", ...},
            description="app.py의 hello 함수 수정",
        )
        # 클라이언트가 /api/approval/{request_id}로 응답
        decision = manager.wait_for_decision(request.request_id)
        if decision == ApprovalDecision.APPROVE:
            execute_tool()
    """

    def __init__(self, default_timeout_sec: int = 120):
        """Initialize the ApprovalManager.

        Args:
            default_timeout_sec: 승인 대기 타임아웃 (기본 120초).

        """
        self._pending: dict[str, ApprovalRequest] = {}
        self._futures: dict[str, asyncio.Future] = {}
        self._always_allowed: set[str] = set()  # "항상 허용"된 도구들
        self._default_timeout = default_timeout_sec
        self._event_loop: asyncio.AbstractEventLoop | None = None

    def is_always_allowed(self, tool_name: str) -> bool:
        """해당 도구가 '항상 허용'으로 설정되었는지 확인."""
        return tool_name in self._always_allowed

    def request_approval(
        self,
        tool_name: str,
        tool_args: dict[str, Any],
        risk_level: str = "medium",
        description: str = "",
        project_root: str | None = None,
    ) -> ApprovalRequest:
        """새로운 승인 요청을 생성합니다.

        Args:
            tool_name: 도구 이름
            tool_args: 도구 인자
            risk_level: 위험도 (safe/low/medium/high/critical)
            description: 사람이 읽을 수 있는 설명
            project_root: diff 생성용 프로젝트 루트

        Returns:
            ApprovalRequest (PENDING 상태)
        """
        # "항상 허용"된 도구는 자동 승인
        if self.is_always_allowed(tool_name):
            return ApprovalRequest(
                request_id="auto-" + uuid.uuid4().hex[:8],
                tool_name=tool_name,
                tool_args=tool_args,
                risk_level=risk_level,
                description=description,
                status=ApprovalStatus.ALWAYS_ALLOW,
                resolved_at=time.time(),
            )

        # diff 미리보기 생성 (파일 편집 도구)
        diff_preview = self._generate_diff_preview(tool_name, tool_args, project_root)

        request = ApprovalRequest(
            request_id=uuid.uuid4().hex,
            tool_name=tool_name,
            tool_args=tool_args,
            risk_level=risk_level,
            description=description or f"{tool_name} 실행",
            diff_preview=diff_preview,
            timeout_sec=self._default_timeout,
        )

        self._pending[request.request_id] = request
        logger.info(
            "[Approval] 승인 요청 생성: %s (%s, risk=%s)",
            request.request_id,
            tool_name,
            risk_level,
        )
        return request

    def resolve(self, request_id: str, decision: ApprovalDecision) -> bool:
        """사용자의 결정을 처리합니다.

        Args:
            request_id: 승인 요청 ID
            decision: 사용자 결정 (approve/deny/always_allow)

        Returns:
            성공 여부
        """
        request = self._pending.get(request_id)
        if request is None or request.status != ApprovalStatus.PENDING:
            logger.warning("[Approval] 알 수 없거나 이미 해결된 요청: %s", request_id)
            return False

        request.resolved_at = time.time()

        if decision == ApprovalDecision.APPROVE:
            request.status = ApprovalStatus.APPROVED
        elif decision == ApprovalDecision.DENY:
            request.status = ApprovalStatus.DENIED
        elif decision == ApprovalDecision.ALWAYS_ALLOW:
            request.status = ApprovalStatus.ALWAYS_ALLOW
            self._always_allowed.add(request.tool_name)
            logger.info("[Approval] '항상 허용' 추가: %s", request.tool_name)

        # 대기 중인 Future 해결
        future = self._futures.pop(request_id, None)
        if future and not future.done():
            future.set_result(request.status)

        logger.info(
            "[Approval] 해결: %s → %s",
            request_id,
            request.status.value,
        )
        return True

    async def wait_for_decision(self, request_id: str) -> ApprovalStatus:
        """승인 결정을 비동기로 대기합니다.

        타임아웃 시 자동으로 DENY(안전 기본값).

        Args:
            request_id: 승인 요청 ID

        Returns:
            최종 ApprovalStatus
        """
        request = self._pending.get(request_id)
        if request is None:
            return ApprovalStatus.DENIED

        # 이미 해결된 경우
        if request.status != ApprovalStatus.PENDING:
            return request.status

        # Future 생성
        loop = asyncio.get_event_loop()
        future = loop.create_future()
        self._futures[request_id] = future

        try:
            # 타임아웃과 함께 대기
            return await asyncio.wait_for(future, timeout=request.timeout_sec)
        except asyncio.TimeoutError:
            request.status = ApprovalStatus.TIMEOUT
            request.resolved_at = time.time()
            logger.warning("[Approval] 타임아웃 자동 거부: %s", request_id)
            return ApprovalStatus.TIMEOUT

    def get_pending(self) -> list[ApprovalRequest]:
        """대기 중인 승인 요청 목록."""
        # 만료된 요청 정리
        expired = [rid for rid, req in self._pending.items() if req.is_expired]
        for rid in expired:
            req = self._pending[rid]
            req.status = ApprovalStatus.TIMEOUT
            req.resolved_at = time.time()
            future = self._futures.pop(rid, None)
            if future and not future.done():
                future.set_result(ApprovalStatus.TIMEOUT)

        return [req for req in self._pending.values() if req.status == ApprovalStatus.PENDING]

    def get_request(self, request_id: str) -> ApprovalRequest | None:
        """특정 승인 요청 조회."""
        return self._pending.get(request_id)

    def clear_resolved(self) -> int:
        """해결된 요청 정리 (메모리 관리)."""
        before = len(self._pending)
        self._pending = {rid: req for rid, req in self._pending.items() if req.status == ApprovalStatus.PENDING}
        cleared = before - len(self._pending)
        if cleared > 0:
            logger.debug("[Approval] 해결된 요청 %s개 정리", cleared)
        return cleared

    def reset_always_allowed(self) -> None:
        """'항상 허용' 목록 초기화."""
        self._always_allowed.clear()
        logger.info("[Approval] '항상 허용' 목록 초기화")

    # ─── diff 미리보기 생성 ──────────────────────────────────────────

    @staticmethod
    def _generate_diff_preview(
        tool_name: str,
        tool_args: dict[str, Any],
        project_root: str | None,
    ) -> str:
        """파일 편집 도구의 diff 미리보기를 생성합니다."""
        # 파일 편집 도구만 diff 생성
        edit_tools = {"edit_file", "apply_patch", "multi_replace_file_content", "write_file"}
        if tool_name not in edit_tools:
            return ""

        # apply_patch는 file_path가 아니라 patch 텍스트를 직접 사용
        if tool_name == "apply_patch":
            patch = tool_args.get("patch", "")
            if patch:
                return patch[:2000] + ("\n... (truncated)" if len(patch) > 2000 else "")
            return ""

        file_path = tool_args.get("file_path", "")
        if not file_path:
            return ""

        # 절대 경로 변환
        if project_root and not os.path.isabs(file_path):
            file_path = os.path.join(project_root, file_path)

        try:
            # edit_file: old_str → new_str diff
            if tool_name == "edit_file":
                old_str = tool_args.get("old_str", "")
                new_str = tool_args.get("new_str", "")
                if old_str and new_str:
                    diff = difflib.unified_diff(
                        old_str.splitlines(keepends=True),
                        new_str.splitlines(keepends=True),
                        fromfile=f"{file_path} (before)",
                        tofile=f"{file_path} (after)",
                        n=3,
                    )
                    return "".join(diff)

            # write_file: 전체 파일 내용
            elif tool_name == "write_file":
                content = tool_args.get("content", "")
                if os.path.exists(file_path):
                    with open(file_path, encoding="utf-8") as f:
                        old_content = f.read()
                    diff = difflib.unified_diff(
                        old_content.splitlines(keepends=True),
                        content.splitlines(keepends=True),
                        fromfile=f"{file_path} (before)",
                        tofile=f"{file_path} (after)",
                        n=3,
                    )
                    return "".join(diff)
                else:
                    return f"**새 파일 생성:**\n```\n{content[:1500]}\n```"

        except Exception:
            logger.debug("diff 미리보기 생성 실패 (non-critical)", exc_info=True)

        return ""


# ─── 싱글톤 ─────────────────────────────────────────────────────────

_approval_manager: ApprovalManager | None = None


def get_approval_manager() -> ApprovalManager:
    """ApprovalManager 싱글톤을 반환합니다."""
    global _approval_manager
    if _approval_manager is None:
        _approval_manager = ApprovalManager()
    return _approval_manager


def reset_approval_manager() -> None:
    """테스트용 — ApprovalManager 재초기화."""
    global _approval_manager
    _approval_manager = None
