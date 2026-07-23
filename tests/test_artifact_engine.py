"""Tests for ArtifactEngine — plan artifact CRUD, validation, and task extraction.

Covers:
- __init__: directory creation
- write_artifact: success and failure
- read_artifact: existing and missing
- delete_artifact: success, missing, and failure
- validate_plan_complete: complete, incomplete, missing file
- is_plan_ready_for_build: readiness check
- extract_plan_tasks: with various task formats
"""

from __future__ import annotations

from pathlib import Path

import pytest

from antigravity_k.engine.artifact_engine import (
    ArtifactEngine,
    ArtifactMetadata,
    PlanTask,
    PlanValidationResult,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def tmp_project(tmp_path: Path) -> str:
    """Create a temporary project root."""
    return str(tmp_path / "project")


@pytest.fixture
def engine(tmp_project: str) -> ArtifactEngine:
    """Create an ArtifactEngine pointing at the temp project."""
    return ArtifactEngine(project_root=tmp_project)


# ---------------------------------------------------------------------------
# PlanTask
# ---------------------------------------------------------------------------


class TestPlanTask:
    """PlanTask dataclass basics."""

    def test_defaults(self):
        task = PlanTask(title="test task")
        assert task.title == "test task"
        assert task.status == "todo"
        assert task.priority == 0

    def test_to_dict(self):
        task = PlanTask(title="my task", description="do it", priority=2, status="done")
        d = task.to_dict()
        assert d["title"] == "my task"
        assert d["priority"] == 2
        assert d["status"] == "done"


# ---------------------------------------------------------------------------
# PlanValidationResult
# ---------------------------------------------------------------------------


class TestPlanValidationResult:
    """PlanValidationResult basics."""

    def test_to_dict(self):
        r = PlanValidationResult(is_complete=True, score=0.85, task_count=5)
        d = r.to_dict()
        assert d["is_complete"] is True
        assert d["score"] == 0.85
        assert d["task_count"] == 5


# ---------------------------------------------------------------------------
# ArtifactEngine — __init__
# ---------------------------------------------------------------------------


class TestInit:
    def test_creates_artifacts_dir(self, tmp_project: str):
        """The artifacts directory should be created on init."""
        artifacts_dir = Path(tmp_project) / "artifacts"
        assert not artifacts_dir.exists()

        ArtifactEngine(project_root=tmp_project)

        assert artifacts_dir.is_dir()

    def test_uses_existing_artifacts_dir(self, tmp_project: str):
        """If the artifacts dir already exists, init should succeed."""
        artifacts_dir = Path(tmp_project) / "artifacts"
        artifacts_dir.mkdir(parents=True)

        engine = ArtifactEngine(project_root=tmp_project)
        assert engine.artifacts_dir == str(artifacts_dir)


# ---------------------------------------------------------------------------
# ArtifactEngine — write_artifact
# ---------------------------------------------------------------------------


class TestWriteArtifact:
    def test_writes_artifact_success(self, engine: ArtifactEngine):
        """A successful write should return success=True and the filepath."""
        content = "# Test Plan\n\nThis is a test plan."
        result = engine.write_artifact("test_plan", content)

        assert result["success"] is True
        assert "test_plan.md" in result["filepath"]
        assert "Artifact" in result["message"]

        # Verify file was written
        filepath = Path(result["filepath"])
        assert filepath.exists()
        assert filepath.read_text(encoding="utf-8") == content

    def test_writes_with_extension(self, engine: ArtifactEngine):
        """Writing with .md extension should not add another .md."""
        result = engine.write_artifact("plan.md", "# Plan")
        assert result["filepath"].endswith("plan.md")

    def test_writes_with_metadata_request_feedback(self, engine: ArtifactEngine):
        """When metadata has request_feedback=True, the message should include approval marker."""
        metadata = ArtifactMetadata(artifact_type="implementation_plan", summary="test", request_feedback=True)
        result = engine.write_artifact("approval_plan", "# Plan", metadata=metadata)

        assert result["success"] is True
        assert "APPROVAL REQUIRED" in result["message"]
        assert result["request_feedback"] is True

    def test_write_failure_returns_error(self, engine: ArtifactEngine):
        """When write fails (permission error), error should be returned."""
        # Point to a read-only directory (non-existent shouldn't fail, os error would)
        with pytest.raises((PermissionError, OSError)):
            # Trigger failure by making artifacts_dir a file instead of dir
            Path(engine.artifacts_dir).write_text("", encoding="utf-8")
            engine.write_artifact("fail_plan", "# Fail")


# ---------------------------------------------------------------------------
# ArtifactEngine — read_artifact
# ---------------------------------------------------------------------------


class TestReadArtifact:
    def test_reads_existing_artifact(self, engine: ArtifactEngine):
        engine.write_artifact("my_plan", "# My Plan\nContent here")
        content = engine.read_artifact("my_plan")
        assert content is not None
        assert "# My Plan" in content

    def test_reads_with_extension(self, engine: ArtifactEngine):
        engine.write_artifact("plan.md", "# Plan")
        content = engine.read_artifact("plan.md")
        assert content is not None

    def test_returns_none_for_missing(self, engine: ArtifactEngine):
        content = engine.read_artifact("nonexistent")
        assert content is None


# ---------------------------------------------------------------------------
# ArtifactEngine — delete_artifact
# ---------------------------------------------------------------------------


class TestDeleteArtifact:
    def test_deletes_existing(self, engine: ArtifactEngine):
        engine.write_artifact("to_delete", "# Delete me")
        assert engine.delete_artifact("to_delete") is True
        assert engine.read_artifact("to_delete") is None

    def test_returns_false_for_missing(self, engine: ArtifactEngine):
        assert engine.delete_artifact("does_not_exist") is False

    def test_deletes_with_extension(self, engine: ArtifactEngine):
        engine.write_artifact("del.md", "# Delete")
        assert engine.delete_artifact("del.md") is True


# ---------------------------------------------------------------------------
# ArtifactEngine — validate_plan_complete
# ---------------------------------------------------------------------------


class TestValidatePlanComplete:
    def test_complete_plan_passes(self, engine: ArtifactEngine):
        """A plan with all required sections, >200 chars, and file refs should pass."""
        content = """# 개요

This project requires a complete refactoring of the authentication module.
The current implementation uses a legacy JWT approach that needs updating.

# 기술 접근

Using Python 3.13 and FastAPI with async middleware.
The new approach will use PBKDF2-based PIN hashing and constant-time comparison.

# 구현 단계

First, we will update the authentication flow.
Then, we will add token verification middleware.

- [ ] Task 1: Update auth routes in `src/antigravity_k/api/auth_routes.py`
- [ ] Task 2: Add verify endpoint to `src/antigravity_k/api/server.py`
- [x] Task 3: Write tests in `tests/test_auth.py`

# 일정

Two weeks for full implementation with testing.
"""
        engine.write_artifact("implementation_plan", content)
        result = engine.validate_plan_complete()
        assert result.is_complete is True
        assert result.score >= 0.6

    def test_missing_file_returns_zero_score(self, engine: ArtifactEngine):
        """When the artifact file doesn't exist, score should be 0."""
        result = engine.validate_plan_complete("nonexistent.md")
        assert result.is_complete is False
        assert result.score == 0.0
        assert "not found" in result.missing_sections or "존재하지" in str(result.issues)

    def test_incomplete_plan_fails(self, engine: ArtifactEngine):
        """A plan with missing sections and no tasks should fail."""
        content = "# Just a title\n\nNot enough content."
        engine.write_artifact("implementation_plan", content)
        result = engine.validate_plan_complete()
        assert result.is_complete is False
        assert len(result.missing_sections) > 0

    def test_is_plan_ready_for_build(self, engine: ArtifactEngine):
        """A complete plan should be ready for build mode."""
        content = """# 개요

This project requires a complete refactoring of the auth module.
The current implementation needs updating to support the new security requirements.

# 기술 접근

Using Python 3.13 and FastAPI with async middleware.
The new approach will use PBKDF2-based PIN hashing.

# 구현 단계

First, update the authentication flow.
Then, add token verification middleware.

- [ ] Task 1: Update auth routes in `auth_routes.py`
- [ ] Task 2: Add verify endpoint to `server.py`
- [ ] Task 3: Write tests in `test_auth.py`

# 일정

Two weeks.
"""
        engine.write_artifact("implementation_plan", content)
        assert engine.is_plan_ready_for_build() is True

    def test_incomplete_plan_not_ready(self, engine: ArtifactEngine):
        """An incomplete plan should not be ready for build."""
        engine.write_artifact("implementation_plan", "# Incomplete")
        assert engine.is_plan_ready_for_build() is False


# ---------------------------------------------------------------------------
# ArtifactEngine — extract_plan_tasks
# ---------------------------------------------------------------------------


class TestExtractPlanTasks:
    def test_extracts_simple_tasks(self, engine: ArtifactEngine):
        """Basic checkbox tasks should be extracted."""
        content = """# Tasks

- [ ] First task
- [x] Completed task
- [ ] Another task
"""
        engine.write_artifact("implementation_plan", content)
        tasks = engine.extract_plan_tasks()
        assert len(tasks) == 3

    def test_marks_done_tasks(self, engine: ArtifactEngine):
        """Completed tasks should have status='done'."""
        content = "- [x] Done task"
        engine.write_artifact("implementation_plan", content)
        tasks = engine.extract_plan_tasks()
        assert len(tasks) == 1
        assert tasks[0].status == "done"

    def test_detects_priority(self, engine: ArtifactEngine):
        """Priority markers should be recognized."""
        content = """# Tasks

- [ ] 🔴 Critical task
- [ ] 🟡 Medium task
- [ ] [HIGH] High priority
- [ ] P0: P0 task
- [ ] P1: P1 task
- [ ] Normal task
"""
        engine.write_artifact("implementation_plan", content)
        tasks = engine.extract_plan_tasks()
        assert len(tasks) == 6

    def test_detects_sections(self, engine: ArtifactEngine):
        """Tasks should be grouped by section headers."""
        content = """## Backend

- [ ] API endpoint
- [ ] Database

## Frontend

- [ ] React component
"""
        engine.write_artifact("implementation_plan", content)
        tasks = engine.extract_plan_tasks()
        assert len(tasks) == 3

    def test_no_tasks_returns_empty(self, engine: ArtifactEngine):
        """A plan with no task checkboxes returns empty list."""
        content = "# Just text\n\nNo tasks here."
        engine.write_artifact("implementation_plan", content)
        tasks = engine.extract_plan_tasks()
        assert tasks == []

    def test_missing_file_returns_empty(self, engine: ArtifactEngine):
        tasks = engine.extract_plan_tasks("nonexistent.md")
        assert tasks == []
