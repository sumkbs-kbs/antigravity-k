from antigravity_k.engine.goal_runner import GoalRunner


def test_goal_runner_builds_autonomous_contract():
    runner = GoalRunner(max_iterations=4)

    report = runner.run(
        "대시보드 DOM 기능을 테스트하고 발견된 문제를 개선한 뒤 테스트 리포트를 업데이트해줘",
        context={"tool_count": 12},
    )

    assert report.assessment.domain == "coding"
    assert report.assessment.autonomy_level == "autonomous-with-verification"
    assert report.assessment.confidence >= 0.75
    assert report.judgment.decision == "execute_with_verification"
    assert report.judgment.ready_to_execute is True
    assert any(signal.name == "verification" for signal in report.judgment.signals)
    assert any("정적 분석" in item for item in report.success_criteria)
    assert len(report.steps) == 6

    markdown = runner.render_markdown(report)
    assert "/goal Autonomous Goal Contract" in markdown
    assert "Autonomous Judgment Policy" in markdown
    assert "execute_with_verification" in markdown
    assert "Capability Transfer Matrix" in markdown
    assert "PermissionGate" in markdown


def test_goal_runner_high_risk_goal_is_approval_gated():
    runner = GoalRunner()

    report = runner.run("운영 서버에 배포하고 오래된 데이터를 삭제해줘")

    assert report.assessment.risk_level == "high"
    assert report.assessment.autonomy_level == "approval-gated"
    assert report.judgment.decision == "approval_required"
    assert report.judgment.ready_to_execute is False
    assert "explicit approval for high-risk actions" in report.assessment.missing_inputs
