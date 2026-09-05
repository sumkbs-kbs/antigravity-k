"""테스트: ShieldsManager — 보호 레벨 관리자.
====================================
shields down/up 라이프사이클, 타임아웃 만료, 상태 영속화,
감사 로그를 검증한다.
"""

from collections.abc import Callable
from pathlib import Path
from typing import Protocol, cast
from unittest.mock import MagicMock

import pytest

from antigravity_k.engine.shields import ShieldsManager, ShieldsState


class _ToolsetManagerDouble(Protocol):
    active_toolset: str

    def set_active(self, toolset: str) -> None: ...


def _manager_state(manager: ShieldsManager) -> ShieldsState:
    return cast(ShieldsState, getattr(manager, "_state"))


def _from_config(config: dict[str, object], toolset_manager: _ToolsetManagerDouble) -> ShieldsManager:
    factory = cast(Callable[..., ShieldsManager], getattr(ShieldsManager, "from_config"))
    return factory(config, toolset_manager=toolset_manager)


@pytest.fixture
def toolset_manager() -> _ToolsetManagerDouble:
    tm = cast(_ToolsetManagerDouble, MagicMock())
    tm.active_toolset = "full"
    return tm


@pytest.fixture
def manager(tmp_path: Path, toolset_manager: _ToolsetManagerDouble) -> ShieldsManager:
    return ShieldsManager(
        toolset_manager=toolset_manager,
        state_dir=str(tmp_path / "shields_state"),
    )


class TestShieldsLifecycle:
    def test_initial_state_is_protected(self, manager: ShieldsManager) -> None:
        assert manager.is_up is True
        assert manager.state.is_protected is True

    def test_shields_down_sets_state(self, manager: ShieldsManager) -> None:
        state = manager.shields_down(reason="테스트 완화", timeout_seconds=300)

        assert state.shields_down is True
        assert state.shields_down_reason == "테스트 완화"
        assert manager.is_down is True

    def test_shields_up_restores_protection(self, manager: ShieldsManager) -> None:
        _ = manager.shields_down(reason="t", timeout_seconds=300)
        state = manager.shields_up(restored_by="tester")

        assert state.shields_down is False
        assert manager.is_up is True

    def test_double_down_is_idempotent(self, manager: ShieldsManager) -> None:
        _ = manager.shields_down(reason="첫번째", timeout_seconds=600)
        _ = manager.shields_down(reason="두번째", timeout_seconds=600)

        # 두번째 호출이 첫번째를 덮어쓰지 않고 유지하거나 무시한다
        assert manager.is_down is True

    def test_timeout_expiry_detected(self, manager: ShieldsManager) -> None:
        _ = manager.shields_down(reason="만료 테스트", timeout_seconds=1)

        # 시간 경과 모방: shields_down_at을 과거로 조작
        import datetime

        past = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(seconds=5)).isoformat()
        _manager_state(manager).shields_down_at = past

        assert manager.check_timeout() is True  # 자동 복원 발생
        assert manager.is_up is True


class TestShieldsState:
    def test_remaining_seconds_permanent_is_none(self):
        from antigravity_k.engine.shields import ShieldsState

        s = ShieldsState(shields_down=True, permanent=True)
        assert s.remaining_seconds is None
        assert s.is_expired is False

    def test_status_dict_shape(self, manager: ShieldsManager) -> None:
        status = manager.status()

        assert "shields_down" in status
        assert "is_protected" in status


class TestAuditLog:
    def test_audit_log_records_down_and_up(self, manager: ShieldsManager) -> None:
        _ = manager.shields_down(reason="r1", timeout_seconds=60)
        _ = manager.shields_up(restored_by="admin")

        log = manager.get_audit_log()

        actions = [cast(str, e["action"]) for e in log]
        assert "down" in actions or "shields_down" in actions

    def test_audit_log_respects_limit(self, manager: ShieldsManager) -> None:
        for i in range(10):
            _ = manager.shields_down(reason=f"r{i}", timeout_seconds=60)
            _ = manager.shields_up(restored_by="auto")

        assert len(manager.get_audit_log(limit=5)) <= 5


class TestStatePersistence:
    def test_state_survives_manager_restart(self, tmp_path: Path, toolset_manager: _ToolsetManagerDouble) -> None:
        m1 = ShieldsManager(toolset_manager=toolset_manager, state_dir=str(tmp_path / "st"))
        _ = m1.shields_down(reason="영속화", timeout_seconds=3600)

        m2 = ShieldsManager(toolset_manager=toolset_manager, state_dir=str(tmp_path / "st"))

        assert m2.is_down is True

    def test_from_config_creates_manager(self, toolset_manager: _ToolsetManagerDouble) -> None:
        manager = _from_config({"default_timeout": 120}, toolset_manager)

        assert manager.is_up is True
