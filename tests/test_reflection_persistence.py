from unittest.mock import MagicMock

from antigravity_k.engine.cognitive_loop import CognitiveLoop


class TestReflectionPersistence:
    def test_reflect_with_high_failure_rate_records_lesson_to_failure_memory(self):
        # Given: a cognitive loop with a failure memory and a step history showing high failure.
        loop = CognitiveLoop()
        loop.failure_memory = MagicMock()
        loop._retry_count = 0
        loop._max_retries = 2
        loop._step_history = [
            {"tool": "run_bash_command", "passed": False, "grade": "fail", "issues": ["exit 1"]},
            {"tool": "run_bash_command", "passed": False, "grade": "fail", "issues": ["exit 2"]},
            {"tool": "run_bash_command", "passed": False, "grade": "fail", "issues": ["timeout"]},
        ]

        # When: reflection runs on a task with a predominantly-failed step history.
        result = loop.reflect("build the project", "output with errors")

        # Then: the lesson is persisted to failure memory so a future task with the same
        # pattern can recall it, instead of being computed and thrown away.
        assert len(result.lessons) >= 1
        assert loop.failure_memory.record.called

    def test_reflect_with_no_failures_does_not_record_spurious_lessons(self):
        loop = CognitiveLoop()
        loop.failure_memory = MagicMock()
        loop._step_history = [
            {"tool": "read_file", "passed": True, "grade": "excellent", "issues": []},
        ]

        result = loop.reflect("read a file", "done")

        assert result.lessons == []
        assert not loop.failure_memory.record.called
