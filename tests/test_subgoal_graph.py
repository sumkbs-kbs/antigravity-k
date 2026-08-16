"""Unit tests for SubgoalGraph."""

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
