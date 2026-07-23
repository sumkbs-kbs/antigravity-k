"""ApprovalManager 단위 테스트 (작업 A).

승인 요청 생성/해결, 항상 허용, 타임아웃, diff 미리보기를 검증합니다.
"""

import pytest

from antigravity_k.engine.approval_manager import (
    ApprovalDecision,
    ApprovalManager,
    ApprovalStatus,
    get_approval_manager,
    reset_approval_manager,
)


@pytest.fixture
def manager():
    """각 테스트마다 깨끗한 ApprovalManager 인스턴스."""
    m = ApprovalManager(default_timeout_sec=10)
    yield m


class TestApprovalRequest:
    """승인 요청 생성 검증."""

    def test_request_creates_pending(self, manager):
        req = manager.request_approval(
            tool_name="edit_file",
            tool_args={"file_path": "app.py", "old_str": "x", "new_str": "y"},
            risk_level="medium",
        )
        assert req.status == ApprovalStatus.PENDING
        assert req.tool_name == "edit_file"
        assert req.request_id  # 비어있지 않은 ID

    def test_request_generates_diff_for_edit(self, manager):
        req = manager.request_approval(
            tool_name="edit_file",
            tool_args={"file_path": "app.py", "old_str": "x=1", "new_str": "x=2"},
        )
        assert "app.py" in req.diff_preview

    def test_request_no_diff_for_non_edit_tool(self, manager):
        req = manager.request_approval(
            tool_name="run_bash_command",
            tool_args={"command": "ls"},
        )
        assert req.diff_preview == ""

    def test_request_in_pending_list(self, manager):
        manager.request_approval("edit_file", {"file_path": "x"}, "medium")
        pending = manager.get_pending()
        assert len(pending) == 1


class TestApprovalResolution:
    """승인 해결 검증."""

    def test_approve(self, manager):
        req = manager.request_approval("edit_file", {"file_path": "x"}, "medium")
        ok = manager.resolve(req.request_id, ApprovalDecision.APPROVE)
        assert ok
        assert req.status == ApprovalStatus.APPROVED

    def test_deny(self, manager):
        req = manager.request_approval("edit_file", {"file_path": "x"}, "medium")
        manager.resolve(req.request_id, ApprovalDecision.DENY)
        assert req.status == ApprovalStatus.DENIED

    def test_resolve_unknown_returns_false(self, manager):
        ok = manager.resolve("nonexistent-id", ApprovalDecision.APPROVE)
        assert not ok

    def test_resolve_already_resolved_returns_false(self, manager):
        req = manager.request_approval("edit_file", {"file_path": "x"}, "medium")
        manager.resolve(req.request_id, ApprovalDecision.APPROVE)
        # 두 번째 해결 시도
        ok = manager.resolve(req.request_id, ApprovalDecision.DENY)
        assert not ok
        assert req.status == ApprovalStatus.APPROVED  # 첫 결정 유지


class TestAlwaysAllowed:
    """'항상 허용' 기능 검증."""

    def test_always_allow_adds_to_set(self, manager):
        req = manager.request_approval("write_file", {"file_path": "x"}, "low")
        manager.resolve(req.request_id, ApprovalDecision.ALWAYS_ALLOW)
        assert manager.is_always_allowed("write_file")

    def test_always_allowed_auto_approves(self, manager):
        req1 = manager.request_approval("write_file", {"file_path": "a"}, "low")
        manager.resolve(req1.request_id, ApprovalDecision.ALWAYS_ALLOW)
        # 두 번째 요청은 자동 승인
        req2 = manager.request_approval("write_file", {"file_path": "b"}, "low")
        assert req2.status == ApprovalStatus.ALWAYS_ALLOW

    def test_reset_always_allowed(self, manager):
        req = manager.request_approval("write_file", {"file_path": "x"}, "low")
        manager.resolve(req.request_id, ApprovalDecision.ALWAYS_ALLOW)
        manager.reset_always_allowed()
        assert not manager.is_always_allowed("write_file")


class TestDiffPreview:
    """diff 미리보기 생성 검증."""

    def test_edit_file_diff(self, manager):
        req = manager.request_approval(
            "edit_file",
            {"file_path": "app.py", "old_str": "x=1", "new_str": "x=2"},
        )
        assert req.diff_preview
        assert "app.py" in req.diff_preview

    def test_write_file_new_file(self, manager, tmp_path):
        new_file = tmp_path / "new.py"
        req = manager.request_approval(
            "write_file",
            {"file_path": str(new_file), "content": "def f():\n    return 1\n"},
        )
        assert "새 파일 생성" in req.diff_preview

    def test_apply_patch_preview(self, manager):
        patch = "*** Begin Patch\n*** Update File: app.py\n@@ x\n-x\n+y\n*** End Patch"
        req = manager.request_approval("apply_patch", {"patch": patch})
        assert "Begin Patch" in req.diff_preview


class TestSingleton:
    """get_approval_manager 싱글톤 검증."""

    def test_singleton_returns_same_instance(self):
        reset_approval_manager()
        m1 = get_approval_manager()
        m2 = get_approval_manager()
        assert m1 is m2

    def test_reset_creates_new_instance(self):
        reset_approval_manager()
        m1 = get_approval_manager()
        reset_approval_manager()
        m2 = get_approval_manager()
        assert m1 is not m2
