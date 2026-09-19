"""Unit tests for SubgoalGraph."""

import pytest

from antigravity_k.engine.subgoal_graph import SubgoalGraph, TaskState


def test_subgoal_dag_flow():
    dag = SubgoalGraph(goal="Implement user authentication")

    dag.add_subgoal("t1", "Create user model")
    dag.add_subgoal("t2", "Create password hash helper", depends_on=["t1"])
    dag.add_subgoal("t3", "Create login API route", depends_on=["t1", "t2"])

    # Initially, only t1 should be ready
    ready = dag.get_ready_subgoals()
    assert len(ready) == 1
    assert ready[0].task_id == "t1"

    # Complete t1 -> t2 should become ready, t3 still pending
    dag.complete_subgoal("t1")
    ready = dag.get_ready_subgoals()
    assert [n.task_id for n in ready] == ["t2"]

    # Complete t2 -> t3 becomes ready
    dag.complete_subgoal("t2")
    ready = dag.get_ready_subgoals()
    assert [n.task_id for n in ready] == ["t3"]

    # Complete t3 -> all completed
    dag.complete_subgoal("t3")
    assert dag.is_all_completed() is True


def test_subgoal_failure_propagation():
    dag = SubgoalGraph(goal="Deploy service")
    dag.add_subgoal("build", "Build docker container")
    dag.add_subgoal("deploy", "Deploy to cloud", depends_on=["build"])

    dag.fail_subgoal("build", "Docker daemon not running")
    assert dag.nodes["build"].state == TaskState.FAILED
    assert dag.nodes["deploy"].state == TaskState.BLOCKED


class TestDependencyValidation:
    def test_unknown_dependency_raises(self):
        g = SubgoalGraph("goal")
        g.add_subgoal("a", "task a")
        with pytest.raises(ValueError, match="unknown dependencies"):
            g.add_subgoal("b", "task b", depends_on=["nonexistent"])

    def test_add_dependency_self_reference_rejected(self):
        g = SubgoalGraph("goal")
        g.add_subgoal("a", "task a")
        assert g.add_dependency("a", "a") is False

    def test_add_dependency_cycle_rejected_and_reverted(self):
        g = SubgoalGraph("goal")
        g.add_subgoal("a", "task a")
        g.add_subgoal("b", "task b", depends_on=["a"])
        # a가 b를 의존하게 만들면 a↔b 사이클 — 거부되고 원복되어야 한다
        assert g.add_dependency("a", "b") is False
        assert g.nodes["a"].depends_on == []
        assert g.get_ready_subgoals()[0].task_id == "a"

    def test_add_dependency_valid(self):
        g = SubgoalGraph("goal")
        g.add_subgoal("a", "task a")
        g.add_subgoal("b", "task b")
        assert g.add_dependency("b", "a") is True
        ready_ids = [n.task_id for n in g.get_ready_subgoals()]
        assert "a" in ready_ids and "b" not in ready_ids
