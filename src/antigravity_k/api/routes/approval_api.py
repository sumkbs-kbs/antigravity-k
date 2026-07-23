"""승인(Approval) API 라우트 (P1-3).

대시보드/클라이언트가 대기 중인 승인 요청을 조회하고 응답하는 엔드포인트.
"""

import logging

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from antigravity_k.engine.approval_manager import (
    ApprovalDecision,
    get_approval_manager,
)

logger = logging.getLogger("antigravity_k.api.approval")

router = APIRouter(prefix="/api/approval", tags=["approval"])


class ApprovalResponse(BaseModel):
    """승인 응답 요청 본문."""

    decision: str  # approve / deny / always_allow


@router.get("/pending")
async def list_pending_approvals():
    """대기 중인 승인 요청 목록을 반환합니다."""
    manager = get_approval_manager()
    pending = manager.get_pending()
    return {
        "pending": [req.to_dict() for req in pending],
        "count": len(pending),
    }


@router.get("/{request_id}")
async def get_approval_request(request_id: str):
    """특정 승인 요청의 상세 정보(diff 미리보기 포함)."""
    manager = get_approval_manager()
    request = manager.get_request(request_id)
    if request is None:
        raise HTTPException(status_code=404, detail="승인 요청을 찾을 수 없습니다")
    return request.to_dict()


@router.post("/{request_id}/resolve")
async def resolve_approval(request_id: str, response: ApprovalResponse):
    """승인 요청에 대한 사용자 결정을 처리합니다."""
    manager = get_approval_manager()

    try:
        decision = ApprovalDecision(response.decision)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"잘못된 결정 값: {response.decision}. approve/deny/always_allow 중 하나",
        )

    success = manager.resolve(request_id, decision)
    if not success:
        raise HTTPException(
            status_code=404,
            detail="승인 요청을 찾을 수 없거나 이미 해결되었습니다",
        )

    req = manager.get_request(request_id)
    return {
        "ok": True,
        "request_id": request_id,
        "status": req.status.value if req else "resolved",
    }


@router.post("/reset-always-allowed")
async def reset_always_allowed():
    """'항상 허용' 목록을 초기화합니다 (모든 도구를 다시 승인 필요로)."""
    manager = get_approval_manager()
    manager.reset_always_allowed()
    return {"ok": True, "message": "'항상 허용' 목록이 초기화되었습니다"}
