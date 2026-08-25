"""테스트: ApprovalManager — 위험 도구 승인 흐름.
============================================
승인 요청→결정 해결, '항상 허용' 자동 승인, 타임아웃 자동 거부,
만료 정리, diff 미리보기 생성을 검증한다.
"""

import asyncio
from unittest.mock import patch

import pytest

from antigravity_k.engine.approval_manager import (
    ApprovalDecision,
    ApprovalManager,
    ApprovalStatus,
)


@pytest.fixture
def manager() -> ApprovalManager:
    return ApprovalManager(default_timeout_sec=120)


class TestRequestAndResolve:
    def test_request_creates_pending_with_diff_preview(self, manager, tmp_path):
        target = tmp_path / "app.py"
        target.write_text("print('hi')\n", encoding="utf-8")

        request = manager.request_approval(
            tool_name="edit_file",
            tool_args={"file_path": str(target), "old_string": "hi", "new_string": "bye"},
        )

        assert request.status == ApprovalStatus.PENDING
        assert manager.get_pending() == [request]

    def test_resolve_approve_marks_status_and_returns_true(self, manager):
        request = manager.request_approval(tool_name="run_bash_command", tool_args={})

        assert manager.resolve(request.request_id, ApprovalDecision.APPROVE) is True
        assert request.status == ApprovalStatus.APPROVED

    def test_resolve_unknown_or_reresolved_request_fails(self, manager):
        assert manager.resolve("ghost-id", ApprovalDecision.APPROVE) is False

        request = manager.request_approval(tool_name="run_bash_command", tool_args={})
        manager.resolve(request.request_id, ApprovalDecision.DENY)

        assert manager.resolve(request.request_id, ApprovalDecision.APPROVE) is False

    def test_deny_marks_denied(self, manager):
        request = manager.request_approval(tool_name="run_bash_command", tool_args={})

        manager.resolve(request.request_id, ApprovalDecision.DENY)

        assert request.status == ApprovalStatus.DENIED

    def test_resolve_wakes_waiting_future(self, manager):
        request = manager.request_approval(tool_name="run_bash_command", tool_args={})

        async def scenario() -> ApprovalStatus:
            task = asyncio.create_task(manager.wait_for_decision(request.request_id))
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            manager.resolve(request.request_id, ApprovalDecision.APPROVE)
            return await task

        assert asyncio.run(scenario()) == ApprovalStatus.APPROVED


class TestAlwaysAllow:
    def test_always_allow_decision_persists_and_autoapproves_next(self, manager):
        first = manager.request_approval(tool_name="write_file", tool_args={})
        manager.resolve(first.request_id, ApprovalDecision.ALWAYS_ALLOW)

        second = manager.request_approval(tool_name="write_file", tool_args={})

        assert second.status == ApprovalStatus.ALWAYS_ALLOW
        assert second.resolved_at is not None
        assert manager.is_always_allowed("write_file") is True

    def test_reset_clears_always_allowed(self, manager):
        first = manager.request_approval(tool_name="write_file", tool_args={})
        manager.resolve(first.request_id, ApprovalDecision.ALWAYS_ALLOW)

        manager.reset_always_allowed()

        assert manager.is_always_allowed("write_file") is False


class TestWaitForDecision:
    def test_unknown_request_immediately_denied(self, manager):
        assert asyncio.run(manager.wait_for_decision("nope")) == ApprovalStatus.DENIED

    def test_already_resolved_returns_current_status(self, manager):
        request = manager.request_approval(tool_name="edit_file", tool_args={"file_path": ""})
        manager.resolve(request.request_id, ApprovalDecision.DENY)

        assert asyncio.run(manager.wait_for_decision(request.request_id)) == ApprovalStatus.DENIED

    def test_timeout_automatically_denies(self, tmp_path):
        manager = ApprovalManager(default_timeout_sec=1)
        with patch("antigravity_k.engine.approval_manager.time.time", side_effect=[0.0, 0.0]):
            request = manager.request_approval(tool_name="edit_file", tool_args={"file_path": ""})
            request.timeout_sec = 1

        status = asyncio.run(manager.wait_for_decision(request.request_id))

        assert status == ApprovalStatus.TIMEOUT
        assert request.status == ApprovalStatus.TIMEOUT


class TestExpiryAndCleanup:
    def test_get_pending_sweeps_expired_requests(self, manager):
        request = manager.request_approval(tool_name="edit_file", tool_args={"file_path": ""})

        with patch(
            "antigravity_k.engine.approval_manager.ApprovalRequest.is_expired",
            new_callable=lambda: property(lambda self: True),
        ):
            assert manager.get_pending() == []

        assert request.status == ApprovalStatus.TIMEOUT

    def test_clear_resolved_keeps_only_pending(self, manager):
        approved = manager.request_approval(tool_name="a", tool_args={})
        denied = manager.request_approval(tool_name="b", tool_args={})
        pending = manager.request_approval(tool_name="c", tool_args={})
        manager.resolve(approved.request_id, ApprovalDecision.APPROVE)
        manager.resolve(denied.request_id, ApprovalDecision.DENY)

        cleared = manager.clear_resolved()

        assert cleared == 2
        assert list(manager._pending) == [pending.request_id]


# ─── diff 미리보기 ────────────────────────────────────────────────


class TestDiffPreview:
    def test_non_edit_tools_have_no_diff(self, manager):
        request = manager.request_approval(tool_name="web_search", tool_args={"query": "x"})

        assert request.diff_preview == ""

    def test_apply_patch_uses_patch_text_truncated(self, manager):
        long_patch = "p" * 3000

        preview = ApprovalManager._generate_diff_preview("apply_patch", {"patch": long_patch}, project_root=None)

        assert preview.startswith("pppp")
        assert len(preview) < 2100
        assert "(truncated)" in preview

    def test_missing_file_yields_empty_diff(self, manager):
        request = manager.request_approval(
            tool_name="edit_file",
            tool_args={"file_path": ""},
            project_root=None,
        )

        assert request.diff_preview == ""

    def test_relative_path_resolved_against_project_root(self, manager, tmp_path):
        preview = ApprovalManager._generate_diff_preview(
            "edit_file",
            {"file_path": "app.py", "old_str": "value = 1\n", "new_str": "value = 2\n"},
            project_root=str(tmp_path),
        )

        assert "-value = 1" in preview
        assert "+value = 2" in preview
        assert "app.py (before)" in preview
