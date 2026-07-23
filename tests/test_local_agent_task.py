"""Tests for local_agent_task.py — LocalAgentTask."""

import time

from antigravity_k.tasks.local_agent_task import LocalAgentTask


class TestLocalAgentTaskInit:
    def test_initial_state_defaults(self):
        def dummy():
            pass

        task = LocalAgentTask(name="test", target=dummy)
        assert task.name == "test"
        assert task.target is dummy
        assert task.args == ()
        assert task.kwargs == {}
        assert task.result is None
        assert task.error is None
        assert task.status == "PENDING"

    def test_initial_state_with_args(self):
        def dummy(a, b):
            return a + b

        task = LocalAgentTask(name="add", target=dummy, args=(1, 2), kwargs={"c": 3})
        assert task.name == "add"
        assert task.args == (1, 2)
        assert task.kwargs == {"c": 3}

    def test_initial_state_empty_kwargs(self):
        def dummy():
            pass

        task = LocalAgentTask(name="empty", target=dummy, kwargs=None)
        assert task.kwargs == {}

    def test_multiple_tasks_independent(self):
        def dummy():
            pass

        t1 = LocalAgentTask(name="a", target=dummy)
        t2 = LocalAgentTask(name="b", target=dummy)
        assert t1.status == "PENDING"
        assert t2.status == "PENDING"
        assert t1.name != t2.name


class TestLocalAgentTaskRun:
    def test_successful_execution(self):
        def add(a, b):
            return a + b

        task = LocalAgentTask(name="add", target=add, args=(3, 4))
        task.run()
        assert task.status == "COMPLETED"
        assert task.result == 7
        assert task.error is None

    def test_string_return_value(self):
        task = LocalAgentTask(name="str", target=lambda: "hello world")
        task.run()
        assert task.status == "COMPLETED"
        assert task.result == "hello world"

    def test_dict_return_value(self):
        task = LocalAgentTask(name="dict", target=lambda: {"key": "value", "num": 42})
        task.run()
        assert task.status == "COMPLETED"
        assert task.result["key"] == "value"
        assert task.result["num"] == 42

    def test_none_return_value(self):
        task = LocalAgentTask(name="none", target=lambda: None)
        task.run()
        assert task.status == "COMPLETED"
        assert task.result is None

    def test_list_return_value(self):
        task = LocalAgentTask(name="list", target=lambda: [1, 2, 3])
        task.run()
        assert task.status == "COMPLETED"
        assert task.result == [1, 2, 3]

    def test_execution_with_kwargs(self):
        def greet(name, greeting="Hello"):
            return f"{greeting}, {name}!"

        task = LocalAgentTask(name="greet", target=greet, args=("World",), kwargs={"greeting": "Hi"})
        task.run()
        assert task.status == "COMPLETED"
        assert task.result == "Hi, World!"


class TestLocalAgentTaskFailure:
    def test_runtime_error_captured(self):
        def crash():
            msg = "boom!"
            raise RuntimeError(msg)

        task = LocalAgentTask(name="crash", target=crash)
        task.run()
        assert task.status == "FAILED"
        assert task.result is None
        assert task.error is not None
        assert "RuntimeError" in task.error
        assert "boom!" in task.error

    def test_value_error_captured(self):
        def invalid():
            raise ValueError("invalid input")

        task = LocalAgentTask(name="invalid", target=invalid)
        task.run()
        assert task.status == "FAILED"
        assert "ValueError" in task.error
        assert "invalid input" in task.error

    def test_type_error_captured(self):
        def type_err():
            return 1 + "string"  # type: ignore[operator]

        task = LocalAgentTask(name="type_err", target=type_err)
        task.run()
        assert task.status == "FAILED"
        assert "TypeError" in task.error

    def test_attribute_error_captured(self):
        def attr_err():
            return None.some_method()  # type: ignore[union-attr]

        task = LocalAgentTask(name="attr_err", target=attr_err)
        task.run()
        assert task.status == "FAILED"
        assert "AttributeError" in task.error

    def test_traceback_included(self):
        def level1():
            return level2()

        def level2():
            msg = "deep error"
            raise ValueError(msg)

        task = LocalAgentTask(name="deep", target=level1)
        task.run()
        assert task.status == "FAILED"
        assert "traceback" in task.error.lower() or "Traceback" in task.error
        assert "level1" in task.error
        assert "level2" in task.error


class TestLocalAgentTaskStatusTransitions:
    def test_initial_status_is_pending(self):
        task = LocalAgentTask(name="status_check", target=lambda: 42)
        assert task.status == "PENDING"

    def test_status_completed_on_success(self):
        task = LocalAgentTask(name="ok", target=lambda: 1)
        task.run()
        assert task.status == "COMPLETED"

    def test_status_failed_on_error(self):
        def fail():
            msg = "intentional"
            raise Exception(msg)

        task = LocalAgentTask(name="fail", target=fail)
        task.run()
        assert task.status == "FAILED"

    def test_run_twice_overwrites(self):
        counter: list[int] = [0]

        def increment():
            counter[0] += 1
            return counter[0]

        task = LocalAgentTask(name="counter", target=increment)
        task.run()
        assert task.result == 1
        task.run()
        assert task.result == 2


class TestLocalAgentTaskThreaded:
    """Tests for LocalAgentTask when actually started as a background thread."""

    def test_start_and_join_completed(self):
        def slow_add(a, b):
            time.sleep(0.05)
            return a + b

        task = LocalAgentTask(name="slow_add", target=slow_add, args=(10, 20))
        task.daemon = True
        task.start()
        task.join(timeout=5)
        assert task.status == "COMPLETED"
        assert task.result == 30

    def test_start_and_join_failed(self):
        def slow_crash():
            time.sleep(0.05)
            msg = "thread crash"
            raise ValueError(msg)

        task = LocalAgentTask(name="slow_crash", target=slow_crash)
        task.daemon = True
        task.start()
        task.join(timeout=5)
        assert task.status == "FAILED"
        assert "ValueError" in task.error

    def test_start_and_join_result(self):
        def compute():
            return {"a": 1, "b": 2}

        task = LocalAgentTask(name="compute", target=compute)
        task.daemon = True
        task.start()
        task.join(timeout=5)
        assert task.result == {"a": 1, "b": 2}

    def test_join_timeout_does_not_block(self):
        def short_running():
            time.sleep(0.5)

        task = LocalAgentTask(name="short", target=short_running)
        task.daemon = True
        task.start()
        task.join(timeout=0.02)
        # Thread may or may not have started running yet; at minimum it's not COMPLETED yet
        assert task.status != "COMPLETED"
        # Wait for completion
        task.join(timeout=2)
        assert task.status == "COMPLETED"
