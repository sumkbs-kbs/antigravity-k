"""Tests for the Ambient Watchdog module."""

from pathlib import Path
from threading import Thread
from types import SimpleNamespace
from typing import Callable, cast
from unittest import mock

import pytest

from antigravity_k.engine.ambient_watchdog import AmbientWatchdog
from antigravity_k.engine.heartbeat import HeartbeatMonitor


def _mock_method(value: mock.MagicMock, name: str) -> mock.MagicMock:
    return cast(mock.MagicMock, getattr(value, name))


def _watchdog_call(watchdog: AmbientWatchdog, name: str, *args: object) -> object:
    method = cast(Callable[..., object], getattr(watchdog, name))
    return method(*args)


def _running(watchdog: AmbientWatchdog) -> bool:
    return cast(bool, getattr(watchdog, "_running"))


def _thread(watchdog: AmbientWatchdog) -> Thread | None:
    return cast(Thread | None, getattr(watchdog, "_thread"))


def _heartbeat_counter(watchdog: AmbientWatchdog) -> int:
    return cast(int, getattr(watchdog, "_heartbeat_counter"))


def _set_private(watchdog: AmbientWatchdog, name: str, value: object) -> None:
    setattr(watchdog, name, value)


@pytest.fixture
def mock_model_manager() -> mock.MagicMock:
    """ModelManager 목 객체."""
    mm = mock.MagicMock()
    setattr(_mock_method(mm, "generate"), "return_value", "OK")
    return mm


@pytest.fixture
def mock_vault() -> mock.MagicMock:
    """VaultEngine 목 객체."""
    return mock.MagicMock()


@pytest.fixture
def mock_heartbeat() -> mock.MagicMock:
    """HeartbeatMonitor 목 객체."""
    hb = mock.MagicMock(spec=HeartbeatMonitor)
    setattr(_mock_method(hb, "execute_due_tasks"), "return_value", [])
    return hb


@pytest.fixture
def watchdog(
    mock_model_manager: mock.MagicMock,
    mock_vault: mock.MagicMock,
    mock_heartbeat: mock.MagicMock,
    tmp_path: Path,
) -> AmbientWatchdog:
    """AmbientWatchdog 인스턴스."""
    return AmbientWatchdog(
        project_root="/tmp/test-project",
        model_manager=mock_model_manager,
        vault_engine=mock_vault,
        heartbeat=mock_heartbeat,
        alert_store_path=tmp_path / "operational-alerts.json",
    )


class TestAmbientWatchdog:
    """Tests for AmbientWatchdog class."""

    def test_init(self, watchdog: AmbientWatchdog) -> None:
        """초기화 시 모든 의존성이 올바르게 설정되어야 함."""
        assert watchdog.project_root == "/tmp/test-project"
        assert _running(watchdog) is False
        assert _thread(watchdog) is None
        assert cast(float, getattr(watchdog, "_poll_interval")) == 5.0
        assert cast(float, getattr(watchdog, "_debounce_time")) == 10.0
        assert watchdog.notification_queue == []

    def test_start_stop(self, watchdog: AmbientWatchdog) -> None:
        """start/stop이 정상적으로 동작해야 함."""
        watchdog.start()
        assert _running(watchdog) is True
        thread = _thread(watchdog)
        assert thread is not None
        assert thread.name == "AmbientWatchdog"
        assert thread.daemon is True

        watchdog.stop()
        assert _running(watchdog) is False

    def test_start_idempotent(self, watchdog: AmbientWatchdog) -> None:
        """start()가 중복 호출되어도 한 번만 시작되어야 함."""
        watchdog.start()
        thread_id = id(_thread(watchdog))
        watchdog.start()  # 두 번째 호출
        assert id(_thread(watchdog)) == thread_id  # 동일 스레드

        watchdog.stop()

    def test_get_current_diff_success(self, watchdog: AmbientWatchdog) -> None:
        """git diff가 정상적으로 실행되면 결과를 반환해야 함."""
        with mock.patch(
            "antigravity_k.engine.ambient_watchdog.subprocess.run",
        ) as mock_run:
            setattr(mock_run, "return_value", SimpleNamespace(stdout="diff --git a/file.py b/file.py", returncode=0))

            result = cast(str, _watchdog_call(watchdog, "_get_current_diff"))
            assert result == "diff --git a/file.py b/file.py"

    def test_get_current_diff_exception(self, watchdog: AmbientWatchdog) -> None:
        """git diff 실행 중 예외 발생 시 빈 문자열을 반환해야 함."""
        with mock.patch(
            "antigravity_k.engine.ambient_watchdog.subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            result = cast(str, _watchdog_call(watchdog, "_get_current_diff"))
            assert result == ""

    def test_analyze_proactive_ok(self, watchdog: AmbientWatchdog, mock_model_manager: mock.MagicMock) -> None:
        """변경사항이 정상이면 OK를 반환하고 알림을 큐에 추가하지 않아야 함."""
        _ = _watchdog_call(watchdog, "_analyze_proactively", "print('hello')")
        assert watchdog.notification_queue == []
        _mock_method(mock_model_manager, "generate").assert_called_once()

    def test_analyze_proactive_warning(self, watchdog: AmbientWatchdog, mock_model_manager: mock.MagicMock) -> None:
        """변경사항에 문제가 있으면 알림을 큐에 추가해야 함."""
        setattr(_mock_method(mock_model_manager, "generate"), "return_value", "⚠️ [Proactive Notice] Syntax error found")
        _ = _watchdog_call(watchdog, "_analyze_proactively", "broken code {{{")
        assert len(watchdog.notification_queue) == 1
        assert "Syntax error" in watchdog.notification_queue[0]

    def test_warning_survives_watchdog_restart(
        self,
        mock_model_manager: mock.MagicMock,
        mock_vault: mock.MagicMock,
        mock_heartbeat: mock.MagicMock,
        tmp_path: Path,
    ):
        alert_path = tmp_path / "operational-alerts.json"
        setattr(_mock_method(mock_model_manager, "generate"), "return_value", "⚠️ [Proactive Notice] Syntax error found")
        first_watchdog = AmbientWatchdog(
            project_root=str(tmp_path),
            model_manager=mock_model_manager,
            vault_engine=mock_vault,
            heartbeat=mock_heartbeat,
            alert_store_path=alert_path,
        )

        _ = _watchdog_call(first_watchdog, "_analyze_proactively", "broken code {{{")
        restarted_watchdog = AmbientWatchdog(
            project_root=str(tmp_path),
            model_manager=mock_model_manager,
            vault_engine=mock_vault,
            heartbeat=mock_heartbeat,
            alert_store_path=alert_path,
        )

        notifications = restarted_watchdog.pop_notifications()

        assert len(notifications) == 1
        assert "Syntax error" in notifications[0]
        assert restarted_watchdog.pop_notifications() == []

    def test_analyze_proactive_skips_large_diff(self, watchdog: AmbientWatchdog, mock_model_manager: mock.MagicMock):
        """큰 diff(>10000자)는 분석을 건너뛰어야 함."""
        _ = _watchdog_call(watchdog, "_analyze_proactively", "x" * 10001)
        _mock_method(mock_model_manager, "generate").assert_not_called()
        assert watchdog.notification_queue == []

    def test_analyze_proactive_exception(self, watchdog: AmbientWatchdog, mock_model_manager: mock.MagicMock):
        """분석 중 예외 발생 시 알림을 추가하지 않고 조용히 넘어가야 함."""
        setattr(_mock_method(mock_model_manager, "generate"), "side_effect", RuntimeError("API error"))
        _ = _watchdog_call(watchdog, "_analyze_proactively", "some code")  # 예외가 발생해도 조용히 처리
        assert watchdog.notification_queue == []

    def test_pop_notifications_empty(self, watchdog: AmbientWatchdog):
        """알림이 없을 때 pop_notifications는 빈 리스트를 반환해야 함."""
        assert watchdog.pop_notifications() == []

    def test_pop_notifications_survives_corrupt_alert_store(
        self,
        mock_model_manager: mock.MagicMock,
        mock_vault: mock.MagicMock,
        mock_heartbeat: mock.MagicMock,
        tmp_path: Path,
    ):
        alert_path = tmp_path / "corrupt-alerts.json"
        _ = alert_path.write_text("not-json", encoding="utf-8")
        watchdog = AmbientWatchdog(
            project_root=str(tmp_path),
            model_manager=mock_model_manager,
            vault_engine=mock_vault,
            heartbeat=mock_heartbeat,
            alert_store_path=alert_path,
        )
        watchdog.notification_queue.append("in-memory warning")

        notifications = watchdog.pop_notifications()

        assert notifications == ["in-memory warning"]

    def test_pop_notifications_returns_and_clears(self, watchdog: AmbientWatchdog):
        """pop_notifications는 알림을 반환하고 큐를 비워야 함."""
        watchdog.notification_queue.append("test notification")
        result = watchdog.pop_notifications()
        assert result == ["test notification"]
        assert watchdog.notification_queue == []

    def test_stop_cleans_up_thread(self, watchdog: AmbientWatchdog):
        """stop()이 스레드를 정리해야 함."""
        watchdog.start()
        watchdog.stop()
        assert _running(watchdog) is False

    def test_heartbeat_triggered(self, watchdog: AmbientWatchdog, mock_heartbeat: mock.MagicMock):
        """하트비트가 설정된 카운터에 도달하면 실행되어야 함."""
        _set_private(watchdog, "_heartbeat_counter", 59)  # 1회 남음
        _ = _watchdog_call(watchdog, "_maybe_run_heartbeat")
        _mock_method(mock_heartbeat, "execute_due_tasks").assert_called_once()

    def test_heartbeat_not_triggered_early(self, watchdog: AmbientWatchdog, mock_heartbeat: mock.MagicMock):
        """하트비트 카운터가 60 미만이면 실행되지 않아야 함."""
        _set_private(watchdog, "_heartbeat_counter", 30)
        _ = _watchdog_call(watchdog, "_maybe_run_heartbeat")
        _mock_method(mock_heartbeat, "execute_due_tasks").assert_not_called()

    def test_heartbeat_counter_reset(self, watchdog: AmbientWatchdog):
        """하트비트 실행 후 카운터가 0으로 리셋되어야 함."""
        _set_private(watchdog, "_heartbeat_counter", 59)
        _ = _watchdog_call(watchdog, "_maybe_run_heartbeat")
        assert _heartbeat_counter(watchdog) == 0

    def test_heartbeat_failure_notification(self, watchdog: AmbientWatchdog, mock_heartbeat: mock.MagicMock):
        """하트비트 실패 시 알림 큐에 추가되어야 함."""
        mock_failure = mock.MagicMock()
        mock_failure.success = False
        mock_failure.task_title = "Health Check"
        mock_failure.message = "Disk space low"
        setattr(_mock_method(mock_heartbeat, "execute_due_tasks"), "return_value", [mock_failure])

        _set_private(watchdog, "_heartbeat_counter", 59)
        _ = _watchdog_call(watchdog, "_maybe_run_heartbeat")
        assert len(watchdog.notification_queue) == 1
        assert "Health Check" in watchdog.notification_queue[0]

    def test_heartbeat_all_success(self, watchdog: AmbientWatchdog, mock_heartbeat: mock.MagicMock):
        """하트비트 모두 성공 시 알림이 추가되지 않아야 함."""
        mock_success = mock.MagicMock()
        mock_success.success = True
        setattr(_mock_method(mock_heartbeat, "execute_due_tasks"), "return_value", [mock_success])

        _set_private(watchdog, "_heartbeat_counter", 59)
        _ = _watchdog_call(watchdog, "_maybe_run_heartbeat")
        assert watchdog.notification_queue == []

    def test_heartbeat_exception(self, watchdog: AmbientWatchdog, mock_heartbeat: mock.MagicMock):
        """하트비트 실행 중 예외가 발생해도 조용히 처리되어야 함."""
        setattr(_mock_method(mock_heartbeat, "execute_due_tasks"), "side_effect", RuntimeError("Heartbeat failed"))
        _set_private(watchdog, "_heartbeat_counter", 59)
        _ = _watchdog_call(watchdog, "_maybe_run_heartbeat")  # 예외 발생하지 않음
        assert _running(watchdog) is False  # running 상태 유지
