"""Tests for the Ambient Watchdog module."""

from unittest import mock

import pytest

from antigravity_k.engine.ambient_watchdog import AmbientWatchdog
from antigravity_k.engine.heartbeat import HeartbeatMonitor


@pytest.fixture
def mock_model_manager():
    """ModelManager 목 객체."""
    mm = mock.MagicMock()
    mm.generate.return_value = "OK"
    return mm


@pytest.fixture
def mock_vault():
    """VaultEngine 목 객체."""
    return mock.MagicMock()


@pytest.fixture
def mock_heartbeat():
    """HeartbeatMonitor 목 객체."""
    hb = mock.MagicMock(spec=HeartbeatMonitor)
    hb.execute_due_tasks.return_value = []
    return hb


@pytest.fixture
def watchdog(mock_model_manager, mock_vault, mock_heartbeat):
    """AmbientWatchdog 인스턴스."""
    return AmbientWatchdog(
        project_root="/tmp/test-project",
        model_manager=mock_model_manager,
        vault_engine=mock_vault,
        heartbeat=mock_heartbeat,
    )


class TestAmbientWatchdog:
    """Tests for AmbientWatchdog class."""

    def test_init(self, watchdog):
        """초기화 시 모든 의존성이 올바르게 설정되어야 함."""
        assert watchdog.project_root == "/tmp/test-project"
        assert watchdog._running is False
        assert watchdog._thread is None
        assert watchdog._poll_interval == 5.0
        assert watchdog._debounce_time == 10.0
        assert watchdog.notification_queue == []

    def test_start_stop(self, watchdog):
        """start/stop이 정상적으로 동작해야 함."""
        watchdog.start()
        assert watchdog._running is True
        assert watchdog._thread is not None
        assert watchdog._thread.name == "AmbientWatchdog"
        assert watchdog._thread.daemon is True

        watchdog.stop()
        assert watchdog._running is False

    def test_start_idempotent(self, watchdog):
        """start()가 중복 호출되어도 한 번만 시작되어야 함."""
        watchdog.start()
        thread_id = id(watchdog._thread)
        watchdog.start()  # 두 번째 호출
        assert id(watchdog._thread) == thread_id  # 동일 스레드

        watchdog.stop()

    def test_get_current_diff_success(self, watchdog):
        """git diff가 정상적으로 실행되면 결과를 반환해야 함."""
        with mock.patch(
            "antigravity_k.engine.ambient_watchdog.subprocess.run",
        ) as mock_run:
            mock_run.return_value.stdout = "diff --git a/file.py b/file.py"
            mock_run.return_value.returncode = 0

            result = watchdog._get_current_diff()
            assert result == "diff --git a/file.py b/file.py"

    def test_get_current_diff_exception(self, watchdog):
        """git diff 실행 중 예외 발생 시 빈 문자열을 반환해야 함."""
        with mock.patch(
            "antigravity_k.engine.ambient_watchdog.subprocess.run",
            side_effect=FileNotFoundError("git not found"),
        ):
            result = watchdog._get_current_diff()
            assert result == ""

    def test_analyze_proactive_ok(self, watchdog):
        """변경사항이 정상이면 OK를 반환하고 알림을 큐에 추가하지 않아야 함."""
        watchdog._analyze_proactively("print('hello')")
        assert watchdog.notification_queue == []
        watchdog.model_manager.generate.assert_called_once()

    def test_analyze_proactive_warning(self, watchdog):
        """변경사항에 문제가 있으면 알림을 큐에 추가해야 함."""
        watchdog.model_manager.generate.return_value = "⚠️ [Proactive Notice] Syntax error found"
        watchdog._analyze_proactively("broken code {{{")
        assert len(watchdog.notification_queue) == 1
        assert "Syntax error" in watchdog.notification_queue[0]

    def test_analyze_proactive_skips_large_diff(self, watchdog):
        """큰 diff(>10000자)는 분석을 건너뛰어야 함."""
        watchdog._analyze_proactively("x" * 10001)
        watchdog.model_manager.generate.assert_not_called()
        assert watchdog.notification_queue == []

    def test_analyze_proactive_exception(self, watchdog):
        """분석 중 예외 발생 시 알림을 추가하지 않고 조용히 넘어가야 함."""
        watchdog.model_manager.generate.side_effect = RuntimeError("API error")
        watchdog._analyze_proactively("some code")  # 예외가 발생해도 조용히 처리
        assert watchdog.notification_queue == []

    def test_pop_notifications_empty(self, watchdog):
        """알림이 없을 때 pop_notifications는 빈 리스트를 반환해야 함."""
        assert watchdog.pop_notifications() == []

    def test_pop_notifications_returns_and_clears(self, watchdog):
        """pop_notifications는 알림을 반환하고 큐를 비워야 함."""
        watchdog.notification_queue.append("test notification")
        result = watchdog.pop_notifications()
        assert result == ["test notification"]
        assert watchdog.notification_queue == []

    def test_stop_cleans_up_thread(self, watchdog):
        """stop()이 스레드를 정리해야 함."""
        watchdog.start()
        watchdog.stop()
        assert watchdog._running is False

    def test_heartbeat_triggered(self, watchdog, mock_heartbeat):
        """하트비트가 설정된 카운터에 도달하면 실행되어야 함."""
        watchdog._heartbeat_counter = 59  # 1회 남음
        watchdog._maybe_run_heartbeat()
        mock_heartbeat.execute_due_tasks.assert_called_once()

    def test_heartbeat_not_triggered_early(self, watchdog, mock_heartbeat):
        """하트비트 카운터가 60 미만이면 실행되지 않아야 함."""
        watchdog._heartbeat_counter = 30
        watchdog._maybe_run_heartbeat()
        mock_heartbeat.execute_due_tasks.assert_not_called()

    def test_heartbeat_counter_reset(self, watchdog, mock_heartbeat):
        """하트비트 실행 후 카운터가 0으로 리셋되어야 함."""
        watchdog._heartbeat_counter = 59
        watchdog._maybe_run_heartbeat()
        assert watchdog._heartbeat_counter == 0

    def test_heartbeat_failure_notification(self, watchdog, mock_heartbeat):
        """하트비트 실패 시 알림 큐에 추가되어야 함."""
        mock_failure = mock.MagicMock()
        mock_failure.success = False
        mock_failure.task_title = "Health Check"
        mock_failure.message = "Disk space low"
        mock_heartbeat.execute_due_tasks.return_value = [mock_failure]

        watchdog._heartbeat_counter = 59
        watchdog._maybe_run_heartbeat()
        assert len(watchdog.notification_queue) == 1
        assert "Health Check" in watchdog.notification_queue[0]

    def test_heartbeat_all_success(self, watchdog, mock_heartbeat):
        """하트비트 모두 성공 시 알림이 추가되지 않아야 함."""
        mock_success = mock.MagicMock()
        mock_success.success = True
        mock_heartbeat.execute_due_tasks.return_value = [mock_success]

        watchdog._heartbeat_counter = 59
        watchdog._maybe_run_heartbeat()
        assert watchdog.notification_queue == []

    def test_heartbeat_exception(self, watchdog, mock_heartbeat):
        """하트비트 실행 중 예외가 발생해도 조용히 처리되어야 함."""
        mock_heartbeat.execute_due_tasks.side_effect = RuntimeError("Heartbeat failed")
        watchdog._heartbeat_counter = 59
        watchdog._maybe_run_heartbeat()  # 예외 발생하지 않음
        assert watchdog._running is False  # running 상태 유지
