"""테스트: ApprovalManager — 위험 도구 승인 흐름.
============================================
승인 요청→결정 해결, '항상 허용' 자동 승인, 타임아웃 자동 거부,
만료 정리, diff 미리보기 생성을 검증한다.
"""

import asyncio
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import cast
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


def _pending_ids(manager: ApprovalManager) -> set[str]:
    pending = cast(dict[str, object], getattr(manager, "_pending"))
    return set(pending)


def _generate_diff_preview(
    tool_name: str,
    tool_args: Mapping[str, object],
    project_root: str | None,
) -> str:
    generator = cast(
        Callable[[str, Mapping[str, object], str | None], str],
        getattr(ApprovalManager, "_generate_diff_preview"),
    )
    return generator(tool_name, tool_args, project_root)


def _always_expired(_request: object) -> bool:
    return True


class TestRequestAndResolve:
    def test_request_creates_pending_with_diff_preview(self, manager: ApprovalManager, tmp_path: Path) -> None:
        target = tmp_path / "app.py"
        _ = target.write_text("print('hi')\n", encoding="utf-8")

        request = manager.request_approval(
            tool_name="edit_file",
            tool_args={"file_path": str(target), "old_string": "hi", "new_string": "bye"},
        )

        assert request.status == ApprovalStatus.PENDING
        assert manager.get_pending() == [request]

    def test_resolve_approve_marks_status_and_returns_true(self, manager: ApprovalManager) -> None:
        request = manager.request_approval(tool_name="run_bash_command", tool_args={})

        assert manager.resolve(request.request_id, ApprovalDecision.APPROVE) is True
        assert request.status == ApprovalStatus.APPROVED

    def test_resolve_unknown_or_reresolved_request_fails(self, manager: ApprovalManager) -> None:
        assert manager.resolve("ghost-id", ApprovalDecision.APPROVE) is False

        request = manager.request_approval(tool_name="run_bash_command", tool_args={})
        _ = manager.resolve(request.request_id, ApprovalDecision.DENY)

        assert manager.resolve(request.request_id, ApprovalDecision.APPROVE) is False

    def test_deny_marks_denied(self, manager: ApprovalManager) -> None:
        request = manager.request_approval(tool_name="run_bash_command", tool_args={})

        _ = manager.resolve(request.request_id, ApprovalDecision.DENY)

        assert request.status == ApprovalStatus.DENIED

    def test_resolve_wakes_waiting_future(self, manager: ApprovalManager) -> None:
        request = manager.request_approval(tool_name="run_bash_command", tool_args={})

        async def scenario() -> ApprovalStatus:
            task = asyncio.create_task(manager.wait_for_decision(request.request_id))
            await asyncio.sleep(0)
            await asyncio.sleep(0)
            _ = manager.resolve(request.request_id, ApprovalDecision.APPROVE)
            return await task

        assert asyncio.run(scenario()) == ApprovalStatus.APPROVED


class TestAlwaysAllow:
    def test_always_allow_decision_persists_and_autoapproves_next(self, manager: ApprovalManager) -> None:
        first = manager.request_approval(tool_name="write_file", tool_args={})
        _ = manager.resolve(first.request_id, ApprovalDecision.ALWAYS_ALLOW)

        second = manager.request_approval(tool_name="write_file", tool_args={})

        assert second.status == ApprovalStatus.ALWAYS_ALLOW
        assert second.resolved_at is not None
        assert manager.is_always_allowed("write_file") is True

    def test_reset_clears_always_allowed(self, manager: ApprovalManager) -> None:
        first = manager.request_approval(tool_name="write_file", tool_args={})
        _ = manager.resolve(first.request_id, ApprovalDecision.ALWAYS_ALLOW)

        manager.reset_always_allowed()

        assert manager.is_always_allowed("write_file") is False


class TestWaitForDecision:
    def test_unknown_request_immediately_denied(self, manager: ApprovalManager) -> None:
        assert asyncio.run(manager.wait_for_decision("nope")) == ApprovalStatus.DENIED

    def test_already_resolved_returns_current_status(self, manager: ApprovalManager) -> None:
        request = manager.request_approval(tool_name="edit_file", tool_args={"file_path": ""})
        _ = manager.resolve(request.request_id, ApprovalDecision.DENY)

        assert asyncio.run(manager.wait_for_decision(request.request_id)) == ApprovalStatus.DENIED

    def test_timeout_automatically_denies(self, tmp_path: Path) -> None:
        _ = tmp_path
        manager = ApprovalManager(default_timeout_sec=1)
        with patch("antigravity_k.engine.approval_manager.time.time", side_effect=[0.0, 0.0]):
            request = manager.request_approval(tool_name="edit_file", tool_args={"file_path": ""})
            request.timeout_sec = 1

        status = asyncio.run(manager.wait_for_decision(request.request_id))

        assert status == ApprovalStatus.TIMEOUT
        assert request.status == ApprovalStatus.TIMEOUT


class TestExpiryAndCleanup:
    def test_get_pending_sweeps_expired_requests(self, manager: ApprovalManager) -> None:
        request = manager.request_approval(tool_name="edit_file", tool_args={"file_path": ""})

        with patch(
            "antigravity_k.engine.approval_manager.ApprovalRequest.is_expired",
            new_callable=lambda: property(_always_expired),
        ):
            assert manager.get_pending() == []

        assert request.status == ApprovalStatus.TIMEOUT

    def test_clear_resolved_keeps_only_pending(self, manager: ApprovalManager) -> None:
        approved = manager.request_approval(tool_name="a", tool_args={})
        denied = manager.request_approval(tool_name="b", tool_args={})
        pending = manager.request_approval(tool_name="c", tool_args={})
        _ = manager.resolve(approved.request_id, ApprovalDecision.APPROVE)
        _ = manager.resolve(denied.request_id, ApprovalDecision.DENY)

        cleared = manager.clear_resolved()

        assert cleared == 2
        assert _pending_ids(manager) == {pending.request_id}


# ─── diff 미리보기 ────────────────────────────────────────────────


class TestDiffPreview:
    def test_non_edit_tools_have_no_diff(self, manager: ApprovalManager) -> None:
        request = manager.request_approval(tool_name="web_search", tool_args={"query": "x"})

        assert request.diff_preview == ""

    def test_apply_patch_uses_patch_text_truncated(self, manager: ApprovalManager) -> None:
        _ = manager
        long_patch = "p" * 3000

        preview = _generate_diff_preview("apply_patch", {"patch": long_patch}, project_root=None)

        assert preview.startswith("pppp")
        assert len(preview) < 2100
        assert "(truncated)" in preview

    def test_missing_file_yields_empty_diff(self, manager: ApprovalManager) -> None:
        request = manager.request_approval(
            tool_name="edit_file",
            tool_args={"file_path": ""},
            project_root=None,
        )

        assert request.diff_preview == ""

    def test_relative_path_resolved_against_project_root(self, manager: ApprovalManager, tmp_path: Path) -> None:
        _ = manager
        preview = _generate_diff_preview(
            "edit_file",
            {"file_path": "app.py", "old_str": "value = 1\n", "new_str": "value = 2\n"},
            project_root=str(tmp_path),
        )

        assert "-value = 1" in preview
        assert "+value = 2" in preview
        assert "app.py (before)" in preview
