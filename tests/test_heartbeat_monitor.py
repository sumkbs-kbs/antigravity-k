"""테스트: HeartbeatMonitor — 체크리스트 파싱·실행·Quiet Hours.
============================================
HEARTBEAT.md 마크다운 → 구조화 태스크 변환, 인터벌 파싱(국문/영문),
due 판정, executor 실행/실패 기록, Quiet Hours 차단을 검증한다.
"""

import pytest

from antigravity_k.engine.heartbeat import HeartbeatMonitor


@pytest.fixture
def monitor(tmp_path):
    return HeartbeatMonitor(project_root=str(tmp_path), quiet_hours=(0, 0))  # quiet 비활성


def _write_checklist(tmp_path, content: str):
    (tmp_path / "HEARTBEAT.md").write_text(content, encoding="utf-8")


class TestLoadChecklist:
    def test_missing_file_returns_empty(self, tmp_path):
        assert HeartbeatMonitor(project_root=str(tmp_path)).load_checklist() == []

    def test_parses_sections_and_checkboxes(self, tmp_path):
        _write_checklist(
            tmp_path,
            (
                "## 시스템 상태 확인\n"
                "- [ ] pytest 실행 결과 확인 (매 30분)\n"
                "- [x] API 서버 응답 확인\n"
                "\n"
                "## 대시보드\n"
                "- [ ] 빌드 상태 확인 (every 2 hours)\n"
            ),
        )
        monitor = HeartbeatMonitor(project_root=str(tmp_path))

        tasks = monitor.load_checklist()

        assert len(tasks) == 3
        assert tasks[0].section == "시스템 상태 확인"
        assert tasks[0].interval_minutes == 30
        assert tasks[1].completed is True
        assert tasks[2].section == "대시보드"
        assert tasks[2].interval_minutes == 120
        # 인터벌 표기가 타이틀에서 제거된다
        assert "(매 30분)" not in tasks[0].title

    def test_reload_preserves_last_run_times(self, tmp_path):
        _write_checklist(tmp_path, "- [ ] 주기 작업")
        monitor = HeartbeatMonitor(project_root=str(tmp_path))
        tasks = monitor.load_checklist()
        tasks[0].last_run = 12345.0

        reloaded = monitor.load_checklist()

        assert reloaded[0].last_run == 12345.0


# ─── 인터벌 파싱 ─────────────────────────────────────────────────


class TestIntervalParsing:
    @pytest.mark.parametrize(
        "title,expected",
        [
            ("pytest 실행 (매 30분)", 30),
            ("빌드 확인 (매 2시간)", 120),
            ("응답 확인 (every 2 hours)", 120),
            ("빠른 점검 (every 90 sec)", 1),
            ("느린 점검 (매 45초)", 1),
        ],
    )
    def test_parse_interval(self, monitor, title, expected):
        assert monitor._parse_interval(title) == expected

    def test_no_pattern_falls_back_to_default(self, tmp_path):
        monitor = HeartbeatMonitor(project_root=str(tmp_path), default_interval_minutes=42)
        assert monitor._parse_interval("인터벨 없음") == 42


# ─── due 판정 & 실행 ─────────────────────────────────────────────


class TestExecuteDueTasks:
    def test_never_run_task_is_due_and_executed(self, tmp_path):
        _write_checklist(tmp_path, "- [ ] 작업 A")
        monitor = HeartbeatMonitor(project_root=str(tmp_path))
        monitor.load_checklist()

        results = monitor.execute_due_tasks(executor_fn=lambda title: f"완료: {title}")

        assert len(results) == 1
        assert results[0].success is True
        assert "작업 A" in results[0].message
        # 실행 후 last_run 갱신 → 재호출 시 스킵
        assert monitor.execute_due_tasks(executor_fn=lambda t: "x") == []

    def test_executor_exception_recorded_as_failure(self, tmp_path):
        _write_checklist(tmp_path, "- [ ] 실패할 작업")
        monitor = HeartbeatMonitor(project_root=str(tmp_path))
        monitor.load_checklist()

        def executor(title):
            raise RuntimeError("executor down")

        results = monitor.execute_due_tasks(executor_fn=executor)

        assert results[0].success is False
        assert "executor down" in results[0].message

    def test_completed_tasks_are_never_due(self, tmp_path):
        _write_checklist(tmp_path, "- [x] 완료된 작업")
        monitor = HeartbeatMonitor(project_root=str(tmp_path))
        monitor.load_checklist()

        assert monitor.execute_due_tasks() == []

    def test_history_capped_at_200(self, tmp_path):
        _write_checklist(tmp_path, "- [ ] 반복 작업")
        monitor = HeartbeatMonitor(project_root=str(tmp_path))

        for _ in range(210):
            # reload → force due → execute (이력 200 초과분을 100으로 절단)
            monitor.load_checklist()
            monitor._tasks[0].last_run = 0.0
            monitor.execute_due_tasks(executor_fn=lambda title: "ok")

        assert len(monitor._results_history) <= 200


# ─── Quiet Hours ─────────────────────────────────────────────────


class TestQuietHours:
    def test_midnight_crossing_window(self, tmp_path):
        monitor = HeartbeatMonitor(project_root=str(tmp_path), quiet_hours=(23, 7))
        from antigravity_k.engine import heartbeat as hb

        real_datetime = hb.datetime

        class FakeDT:
            hour = 2  # 새벽 2시 → quiet

            @staticmethod
            def now():
                return FakeDT

        hb.datetime = FakeDT
        try:
            assert monitor.is_quiet_hours() is True
            FakeDT.hour = 12
            assert monitor.is_quiet_hours() is False
        finally:
            hb.datetime = real_datetime

    def test_non_crossing_window(self, tmp_path):
        from antigravity_k.engine import heartbeat as hb

        monitor = HeartbeatMonitor(project_root=str(tmp_path), quiet_hours=(13, 15))
        real_datetime = hb.datetime

        class FakeDT:
            hour = 14

            @staticmethod
            def now():
                return FakeDT

        hb.datetime = FakeDT
        try:
            assert monitor.is_quiet_hours() is True
            FakeDT.hour = 16
            assert monitor.is_quiet_hours() is False
        finally:
            hb.datetime = real_datetime

    def test_quiet_hours_blocks_execution(self, tmp_path):
        from antigravity_k.engine import heartbeat as hb

        _write_checklist(tmp_path, "- [ ] 조용한 시간 작업")
        monitor = HeartbeatMonitor(project_root=str(tmp_path), quiet_hours=(0, 24) if False else (23, 7))
        monitor.load_checklist()

        real_datetime = hb.datetime

        class FakeDT:
            hour = 23

            @staticmethod
            def now():
                return FakeDT

        hb.datetime = FakeDT
        try:
            executed = []
            results = monitor.execute_due_tasks(executor_fn=lambda t: executed.append(t))
            assert results == [] and not executed
        finally:
            hb.datetime = real_datetime


# ─── 상태 보고 ───────────────────────────────────────────────────


class TestGetStatus:
    def test_status_shape(self, tmp_path):
        _write_checklist(tmp_path, "- [ ] 미완료\n- [x] 완료")
        monitor = HeartbeatMonitor(project_root=str(tmp_path))
        monitor.load_checklist()

        status = monitor.get_status()

        assert status["total_tasks"] == 2
        assert status["completed_tasks"] == 1
        assert status["quiet_hours"] is False
        assert "checklist_path" in status
