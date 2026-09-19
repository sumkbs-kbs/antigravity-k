import pytest

from antigravity_k.engine.task_state_types import InvalidTaskStatusError, parse_task_status


@pytest.mark.parametrize(
    "value",
    ["pending", "running", "resuming", "done", "failed", "paused", "cancelled"],
)
def test_parse_task_status_accepts_canonical_values(value):
    assert parse_task_status(value) == value


def test_parse_task_status_rejects_unknown_values():
    with pytest.raises(InvalidTaskStatusError):
        parse_task_status("unknown")
