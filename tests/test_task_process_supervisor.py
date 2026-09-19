from __future__ import annotations

import os
import signal
import subprocess
import sys
import threading
import time

import psutil
import pytest

from antigravity_k.engine.limited_process_runner import LimitedProcessRunner
from antigravity_k.engine.task_execution_context import TaskExecutionContext, bind_task_execution_context
from antigravity_k.engine.task_process_supervisor import task_process_supervisor
from antigravity_k.engine.task_state_store import TaskStateStore


def _live_process_ids(process_ids: tuple[int, ...]) -> tuple[int, ...]:
    live: list[int] = []
    for process_id in process_ids:
        if not psutil.pid_exists(process_id):
            continue
        try:
            if psutil.Process(process_id).status() != psutil.STATUS_ZOMBIE:
                live.append(process_id)
        except psutil.NoSuchProcess:
            continue
    return tuple(live)


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group behavior")
def test_task_cancel_terminates_parent_and_descendant_without_stale_registration(tmp_path):
    task_id = "process-tree-cancel"
    pid_file = tmp_path / "process-tree.pid"
    store = TaskStateStore(str(tmp_path / "tasks.db"))
    program = (
        "import os, pathlib, subprocess, sys, time; "
        "child = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(60)'], "
        "stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL); "
        "pathlib.Path(sys.argv[1]).write_text(f'{os.getpid()} {child.pid}', encoding='utf-8'); "
        "time.sleep(60)"
    )
    runner = LimitedProcessRunner(max_output_bytes=4096)
    failure: list[BaseException] = []

    def execute() -> None:
        try:
            with bind_task_execution_context(TaskExecutionContext(task_id, store)):
                runner.run(
                    [sys.executable, "-c", program, str(pid_file)],
                    shell=False,
                    timeout=60,
                    env=None,
                    cwd=str(tmp_path),
                )
        except BaseException as error:
            failure.append(error)

    thread = threading.Thread(target=execute, name="supervised-process-test")
    thread.start()
    deadline = time.monotonic() + 5
    while not pid_file.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert pid_file.exists()
    process_ids = tuple(int(value) for value in pid_file.read_text(encoding="utf-8").split())

    try:
        assert task_process_supervisor.cancel_task(task_id)
        thread.join(timeout=5)
        assert not thread.is_alive()
        deadline = time.monotonic() + 5
        while _live_process_ids(process_ids) and time.monotonic() < deadline:
            time.sleep(0.01)
        assert _live_process_ids(process_ids) == ()
        assert task_process_supervisor.active_process_count(task_id) == 0
        assert failure == []
    finally:
        for process_id in _live_process_ids(process_ids):
            try:
                os.kill(process_id, signal.SIGKILL)
            except ProcessLookupError:
                pass


@pytest.mark.skipif(os.name != "posix", reason="POSIX process-group behavior")
def test_cancelled_task_rejects_late_process_registration(tmp_path):
    task_id = "late-process"
    store = TaskStateStore(str(tmp_path / "tasks.db"))

    with bind_task_execution_context(TaskExecutionContext(task_id, store)):
        assert task_process_supervisor.cancel_task(task_id)
        process = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(60)"],
            start_new_session=True,
        )
        registration = task_process_supervisor.register(task_id, process, process.pid)
        try:
            process.wait(timeout=2)
            assert process.returncode is not None
        finally:
            task_process_supervisor.terminate(registration)
            task_process_supervisor.unregister(registration)
