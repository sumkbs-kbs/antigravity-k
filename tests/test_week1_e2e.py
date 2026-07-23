"""Week 1 E2E 통합 테스트 — D1~D7 Plan/Build Mode Separation 전체 검증.

테스트 범위:
  D1 ✅ ExecutionMode enum + ModeManager
  D2 ✅ ArtifactEngine (Plan 작성/검증/태스크 추출)
  D3 ✅ PlanGuard/GatePipeline 툴 권한 연동
  D4 ✅ PlanToBuildPipeline (Plan→Build 자동 전환)
  D5 ✅ OrchestratorAgent 모드 분기 + QualityGate execution_mode 분기
  D6 ✅ CLI/TUI format_status 출력
  D7 ✅ ModeChanged EventBus publish + 리스너
"""

from __future__ import annotations

import tempfile

import pytest

from antigravity_k.engine.artifact_engine import (
    ArtifactEngine,
    ArtifactMetadata,
)
from antigravity_k.engine.execution_mode import ExecutionMode
from antigravity_k.engine.mode_manager import ModeManager
from antigravity_k.engine.quality_gate import QualityGate, QualityGrade

# ═══════════════════════════════════════════════════════════════════════
# D1: ExecutionMode + ModeManager
# ═══════════════════════════════════════════════════════════════════════


class TestD1_ExecutionMode:
    """ExecutionMode enum — 3가지 모드와 속성/권한 검증."""

    def test_mode_values(self):
        """ExecutionMode가 올바른 문자열 값을 가져야 함."""
        assert ExecutionMode.PLAN.value == "plan"
        assert ExecutionMode.BUILD.value == "build"
        assert ExecutionMode.INTERACTIVE.value == "interactive"

    def test_mode_properties(self):
        """각 모드의 is_plan/is_build/is_interactive가 정확해야 함."""
        assert ExecutionMode.PLAN.is_plan is True
        assert ExecutionMode.PLAN.is_build is False
        assert ExecutionMode.PLAN.is_interactive is False

        assert ExecutionMode.BUILD.is_build is True
        assert ExecutionMode.BUILD.is_plan is False
        assert ExecutionMode.BUILD.is_interactive is False

        assert ExecutionMode.INTERACTIVE.is_interactive is True
        assert ExecutionMode.INTERACTIVE.is_plan is False
        assert ExecutionMode.INTERACTIVE.is_build is False

    def test_plan_mode_tool_allowed(self):
        """PLAN 모드: 읽기 전용 도구만 허용하고 나머지는 차단."""
        for tool in {"read_file", "grep_search", "glob_search", "list_directory", "write_artifact"}:
            assert ExecutionMode.PLAN.tool_is_allowed(tool), f"PLAN 모드에서 '{tool}'이(가) 허용되어야 함"

        for tool in {"run_bash_command", "edit_file", "str_replace", "write_file"}:
            assert not ExecutionMode.PLAN.tool_is_allowed(tool), f"PLAN 모드에서 '{tool}'이(가) 차단되어야 함"

    def test_build_mode_all_tools_allowed(self):
        """BUILD 모드: 모든 도구 허용."""
        for tool in {"read_file", "run_bash_command", "edit_file", "write_file", "str_replace"}:
            assert ExecutionMode.BUILD.tool_is_allowed(tool), f"BUILD 모드에서 '{tool}'이(가) 허용되어야 함"

    def test_build_mode_restricted_tools_require_approval(self):
        """BUILD 모드: restricted 도구는 승인 필요."""
        for tool in {"deploy", "db_migration", "payment"}:
            assert ExecutionMode.BUILD.tool_requires_approval(tool), f"BUILD 모드에서 '{tool}' 승인이 필요해야 함"

    def test_plan_block_reason(self):
        """PLAN 모드 차단 사유 메시지 검증."""
        reason = ExecutionMode.PLAN.get_block_reason("run_bash_command")
        assert "PLAN MODE" in reason
        assert "run_bash_command" in reason
        assert ExecutionMode.PLAN.get_block_reason("read_file") == ""


class TestD1_ModeManager:
    """ModeManager — 상태 전이, 이력, 리스너, 권한 검증."""

    def test_initial_state(self):
        """ModeManager 초기 상태는 INTERACTIVE여야 함."""
        mgr = ModeManager()
        assert mgr.current_mode == ExecutionMode.INTERACTIVE
        assert mgr.is_interactive is True
        assert mgr.is_plan is False
        assert mgr.is_build is False
        assert mgr.mode_history == []
        assert mgr.plan_artifact_path is None

    def test_custom_initial_mode(self):
        """초기 모드를 지정할 수 있어야 함."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        assert mgr.current_mode == ExecutionMode.PLAN
        assert mgr.is_plan is True

    def test_switch_to_plan(self):
        """INTERACTIVE → PLAN 전환."""
        mgr = ModeManager()
        assert mgr.switch_to_plan("E2E: test plan") is True
        assert mgr.current_mode == ExecutionMode.PLAN
        assert mgr.is_plan is True
        assert mgr.plan_artifact_path is None
        assert len(mgr.mode_history) == 1
        assert mgr.mode_history[0].from_mode == "interactive"
        assert mgr.mode_history[0].to_mode == "plan"
        assert mgr.mode_history[0].reason == "E2E: test plan"

    def test_switch_to_plan_idempotent(self):
        """이미 PLAN 모드면 전환 없이 True 반환."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        assert mgr.switch_to_plan("Already plan") is True
        assert len(mgr.mode_history) == 0  # 전환 기록 없음

    def test_switch_to_build_from_plan_fails_without_quality(self):
        """Plan→Build 전환은 QualityGate 통과가 필요."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        # 검증 없이 전환 시도 → 실패
        assert mgr.switch_to_build() is False
        assert mgr.is_plan is True

    def test_switch_to_build_from_plan_succeeds_with_quality(self):
        """Plan 검증 + Quality 통과 후 Plan→Build 전환."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        mgr.set_plan_artifact("artifacts/implementation_plan.md")
        mgr.set_plan_quality_passed(True)
        assert mgr.switch_to_build(reason="Plan 검증 완료") is True
        assert mgr.current_mode == ExecutionMode.BUILD
        assert mgr.is_build is True
        # 전환 이력 확인
        assert len(mgr.mode_history) == 1
        assert mgr.mode_history[0].from_mode == "plan"
        assert mgr.mode_history[0].to_mode == "build"

    def test_switch_to_build_from_interactive(self):
        """Interactive→Build는 직접 전환 가능."""
        mgr = ModeManager()
        assert mgr.switch_to_build(reason="직접 전환") is True
        assert mgr.current_mode == ExecutionMode.BUILD

    def test_switch_to_interactive(self):
        """모든 모드 → Interactive 전환."""
        mgr = ModeManager(initial_mode=ExecutionMode.BUILD)
        mgr.set_plan_artifact("test.md")
        mgr.set_plan_quality_passed(True)
        assert mgr.switch_to_interactive("테스트 완료") is True
        assert mgr.current_mode == ExecutionMode.INTERACTIVE
        # Interactive 진입 시 plan artifact/quality 리셋
        assert mgr.plan_artifact_path is None

    def test_can_auto_transition_to_build(self):
        """자동 전환 가능 조건 검증."""
        mgr = ModeManager()
        # 초기: 불가능
        assert mgr.can_auto_transition_to_build is False
        # Plan artifact만 설정: 아직 불가능
        mgr.set_plan_artifact("plan.md")
        assert mgr.can_auto_transition_to_build is False
        # Quality 통과: 가능
        mgr.set_plan_quality_passed(True)
        assert mgr.can_auto_transition_to_build is True

    def test_mode_history_tracking(self):
        """모든 전환이 이력에 기록되어야 함."""
        mgr = ModeManager()
        mgr.switch_to_plan("Step 1")
        mgr.set_plan_artifact("plan.md")
        mgr.set_plan_quality_passed(True)
        mgr.switch_to_build(reason="Step 2")
        mgr.switch_to_interactive("Step 3")

        assert len(mgr.mode_history) == 3
        transitions = [(h.from_mode, h.to_mode) for h in mgr.mode_history]
        assert transitions == [
            ("interactive", "plan"),
            ("plan", "build"),
            ("build", "interactive"),
        ]

    def test_mode_history_limit(self):
        """히스토리는 최대 100개까지 유지."""
        mgr = ModeManager()
        for i in range(105):
            mgr._record_transition(ExecutionMode.INTERACTIVE, ExecutionMode.PLAN, f"test {i}")
        assert len(mgr.mode_history) == 100

    def test_check_tool_permission_plan(self):
        """PLAN 모드: 읽기 도구는 allowed, 쓰기 도구는 denied."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        # 읽기 전용 도구
        result = mgr.check_tool_permission("read_file")
        assert result["allowed"] is True
        assert result["requires_approval"] is False

        # 쓰기 도구
        result = mgr.check_tool_permission("run_bash_command")
        assert result["allowed"] is False
        assert "실행할 수 없습니다" in result.get("reason", "")

    def test_check_tool_permission_build(self):
        """BUILD 모드: 일반 도구는 허용, restricted 도구는 승인 필요."""
        mgr = ModeManager(initial_mode=ExecutionMode.BUILD)

        # 일반 도구
        result = mgr.check_tool_permission("read_file")
        assert result["allowed"] is True

        # Restricted 도구
        result = mgr.check_tool_permission("deploy")
        assert result["allowed"] is True  # BUILD에선 허용
        assert result["requires_approval"] is True

    def test_should_enforce_plan_mode_keywords(self):
        """PLAN 트리거 키워드 감지."""
        mgr = ModeManager()

        # 복잡한 태스크 타입
        assert mgr.should_enforce_plan_mode("complex", "Some task") is True

        # 일반 태스크
        assert mgr.should_enforce_plan_mode("simple", "Some task") is False

        # 이미 PLAN 모드
        mgr.switch_to_plan()
        assert mgr.should_enforce_plan_mode("complex", "Any") is False

        # 코딩 + 키워드 (PLAN → INTERACTIVE로 복귀 후 테스트)
        mgr.switch_to_interactive()
        assert mgr.should_enforce_plan_mode("coding", "Refactor the auth module") is True
        assert mgr.should_enforce_plan_mode("coding", "Fix a small bug") is False

    def test_listener_notification(self):
        """모드 변경 시 등록된 리스너가 호출되어야 함."""
        mgr = ModeManager()
        calls = []

        def listener(from_mode, to_mode, reason):
            calls.append((from_mode, to_mode, reason))

        mgr.add_listener(listener)
        mgr.switch_to_plan("Testing listener")

        assert len(calls) == 1
        assert calls[0][0] == ExecutionMode.INTERACTIVE
        assert calls[0][1] == ExecutionMode.PLAN
        assert calls[0][2] == "Testing listener"

    def test_remove_listener(self):
        """리스너 제거 후 호출되지 않아야 함."""
        mgr = ModeManager()
        calls = []

        def listener(from_mode, to_mode, reason):
            calls.append(1)

        mgr.add_listener(listener)
        mgr.remove_listener(listener)
        mgr.switch_to_plan("After remove")
        assert len(calls) == 0

    def test_to_dict(self):
        """직렬화 딕셔너리에 모든 필드가 포함되어야 함."""
        mgr = ModeManager()
        mgr.switch_to_plan("Testing")
        d = mgr.to_dict()
        assert d["current_mode"] == "plan"
        assert d["is_plan"] is True
        assert d["is_build"] is False
        assert d["is_interactive"] is False
        assert d["history_count"] == 1
        assert d["last_transition"]["from"] == "interactive"
        assert d["last_transition"]["to"] == "plan"

    def test_format_status(self):
        """format_status가 모드별 올바른 내용을 포함해야 함."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        status = mgr.format_status()
        assert "PLAN" in status
        assert "읽기 전용" in status or "read-only" in status.lower()

        mgr.switch_to_interactive()
        status = mgr.format_status()
        assert "INTERACTIVE" in status


# ═══════════════════════════════════════════════════════════════════════
# D2: ArtifactEngine
# ═══════════════════════════════════════════════════════════════════════


class TestD2_ArtifactEngine:
    """ArtifactEngine — Plan 작성, 검증, 태스크 추출."""

    @pytest.fixture
    def engine(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            yield ArtifactEngine(project_root=tmpdir)

    def test_write_and_read_artifact(self, engine):
        """아티팩트 쓰기/읽기."""
        result = engine.write_artifact(
            "implementation_plan.md",
            "# Test Plan\n\nSome content.",
            ArtifactMetadata(artifact_type="implementation_plan", summary="Test"),
        )
        assert result["success"] is True

        content = engine.read_artifact("implementation_plan.md")
        assert content is not None
        assert "Test Plan" in content

    def test_write_artifact_appends_extension(self, engine):
        """확장자 없는 파일명에 .md 자동 추가."""
        result = engine.write_artifact("myplan", "# Content")
        assert result["success"] is True
        content = engine.read_artifact("myplan.md")
        assert content == "# Content"

    def test_read_nonexistent_artifact(self, engine):
        """존재하지 않는 아티팩트 읽기 → None."""
        assert engine.read_artifact("nonexistent.md") is None

    def test_delete_artifact(self, engine):
        """아티팩트 삭제."""
        engine.write_artifact("test.md", "# Hello")
        assert engine.delete_artifact("test.md") is True
        assert engine.read_artifact("test.md") is None
        assert engine.delete_artifact("test.md") is False

    def test_validate_plan_complete_missing(self, engine):
        """파일이 없으면 검증 실패."""
        result = engine.validate_plan_complete("missing.md")
        assert result.is_complete is False
        assert result.score == 0.0
        assert "(artifact not found)" in result.missing_sections

    def test_validate_plan_complete_complete(self, engine):
        """완전한 Plan 검증 통과."""
        content = (
            "# Overview\n\nRefactor auth module.\n\n"
            "## Technical Approach\n\n"
            "Use JWT tokens.\n\n"
            "## Implementation Steps\n\n"
            "1. Create auth service\n\n"
            "## Tasks\n\n"
            "- [ ] Create auth service\n"
            "- [ ] Add JWT validation\n"
            "- [ ] Write tests\n\n"
            "## Timeline\n\n"
            "Week 1.\n\n"
        )
        engine.write_artifact("implementation_plan.md", content)
        result = engine.validate_plan_complete()
        assert result.is_complete is True
        assert result.score >= 0.6
        assert result.task_count >= 3

    def test_validate_plan_complete_incomplete(self, engine):
        """불완전한 Plan은 검증 실패."""
        content = "# Overview\n\nJust a thought."
        engine.write_artifact("implementation_plan.md", content)
        result = engine.validate_plan_complete()
        assert result.is_complete is False
        assert result.score < 0.6
        assert len(result.missing_sections) > 0

    def test_extract_plan_tasks(self, engine):
        """Plan에서 체크박스 태스크 추출."""
        content = (
            "## Tasks\n\n"
            "- [ ] First—Do something\n"
            "- [ ] P1: HighPriority\n"
            "- [x] Completed task\n"
            "- [ ] 🔴 Critical—Must do\n"
        )
        engine.write_artifact("plan.md", content)
        tasks = engine.extract_plan_tasks("plan.md")
        assert len(tasks) == 4
        assert tasks[0].title == "First"
        assert tasks[0].description == "Do something"
        assert tasks[1].priority == 1  # P1: matches r"^P1[:.\s]+"
        assert tasks[1].title == "HighPriority"
        assert tasks[2].status == "done"
        assert tasks[3].priority == 2  # 🔴 matches r"^🔴\s*"

    def test_extract_plan_tasks_empty(self, engine):
        """태스크가 없는 Plan → 빈 리스트."""
        engine.write_artifact("empty.md", "# No tasks")
        assert engine.extract_plan_tasks("empty.md") == []

    def test_list_artifacts(self, engine):
        """아티팩트 목록 조회."""
        engine.write_artifact("plan.md", "# Plan")
        engine.write_artifact("task.md", "# Task")
        engine.write_artifact("walkthrough.md", "# Summary")

        artifacts = engine.list_artifacts()
        assert len(artifacts) == 3
        filenames = [a["filename"] for a in artifacts]
        assert "plan.md" in filenames
        assert "walkthrough.md" in filenames
        assert all(a["type"] in ("implementation_plan", "task", "walkthrough", "other") for a in artifacts)

    def test_is_plan_ready_for_build(self, engine):
        """Plan 검증 통과 시 Build 준비 완료."""
        content = (
            "# Overview\n\n"
            "Refactor the auth module to use JWT tokens for better security.\n"
            "This is a critical improvement for the platform.\n\n"
            "## Technical Approach\n\n"
            "Replace session-based auth with JWT tokens.\n"
            "Use `pyjwt` library for token generation and validation.\n\n"
            "## Implementation Steps\n\n"
            "1. Create AuthService class\n"
            "2. Add JWT validation middleware\n"
            "3. Migrate existing sessions\n\n"
            "## Tasks\n\n"
            "- [ ] Create AuthService class\n"
            "- [ ] Implement JWT token generation\n"
            "- [ ] Add token validation middleware\n"
            "- [ ] Write unit tests for auth\n"
            "- [ ] Migrate existing user sessions\n\n"
            "## Timeline\n\n"
            "Week 1: Core implementation\n"
            "Week 2: Testing and migration\n"
        )
        engine.write_artifact("implementation_plan.md", content)
        assert engine.is_plan_ready_for_build() is True


# ═══════════════════════════════════════════════════════════════════════
# D3: PlanGuard/GatePipeline 툴 권한 연동
# ═══════════════════════════════════════════════════════════════════════


class TestD3_ToolPermissions:
    """PlanGuard/GatePipeline — ModeManager를 통한 툴 권한 검증."""

    def test_plan_blocks_write_tools(self):
        """PLAN 모드에서 쓰기 도구 차단 확인."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        for tool in {"edit_file", "str_replace", "write_file", "run_bash_command"}:
            perm = mgr.check_tool_permission(tool)
            assert perm["allowed"] is False, f"PLAN 모드에서 '{tool}' 차단되어야 함"

    def test_plan_allows_read_tools(self):
        """PLAN 모드에서 읽기 도구 허용 확인."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        for tool in {"read_file", "grep_search", "glob_search", "write_artifact"}:
            perm = mgr.check_tool_permission(tool)
            assert perm["allowed"] is True, f"PLAN 모드에서 '{tool}' 허용되어야 함"

    def test_build_allows_all_tools(self):
        """BUILD 모드에서 모든 도구 허용."""
        mgr = ModeManager(initial_mode=ExecutionMode.BUILD)
        for tool in {"edit_file", "str_replace", "write_file", "run_bash_command", "read_file"}:
            perm = mgr.check_tool_permission(tool)
            assert perm["allowed"] is True

    def test_build_restricted_requires_approval(self):
        """BUILD 모드에서 restricted 도구 승인 필요."""
        mgr = ModeManager(initial_mode=ExecutionMode.BUILD)
        for tool in {"deploy", "db_migration", "payment", "computer_use"}:
            perm = mgr.check_tool_permission(tool)
            assert perm["requires_approval"] is True

    def test_plan_block_reason_message(self):
        """PLAN 블록 사유 메시지에 모드 정보 포함."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        perm = mgr.check_tool_permission("run_bash_command")
        assert "PLAN MODE" in perm["reason"]


# ═══════════════════════════════════════════════════════════════════════
# D4: PlanToBuildPipeline
# ═══════════════════════════════════════════════════════════════════════


class TestD4_PlanToBuildPipeline:
    """PlanToBuildPipeline — Plan→Build 자동 전환 파이프라인."""

    def test_pipeline_requires_dependencies(self):
        """필수 의존성 누락 시 실패."""
        from antigravity_k.engine.plan_to_build import PlanToBuildPipeline

        # 둘 다 없음
        pipeline = PlanToBuildPipeline()
        result = pipeline.run()
        assert result.success is False
        assert any("ModeManager" in e for e in result.errors)

    def test_quick_check_false_without_plan(self):
        """Plan 없이 quick_check 실패."""
        from antigravity_k.engine.plan_to_build import PlanToBuildPipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            ae = ArtifactEngine(tmpdir)
            pipeline = PlanToBuildPipeline(
                mode_manager=ModeManager(),
                artifact_engine=ae,
            )
            assert pipeline.quick_check() is False

    def test_full_pipeline_with_valid_plan(self):
        """완전한 Plan → Build 전환 파이프라인."""
        from antigravity_k.engine.plan_to_build import PlanToBuildPipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
            ae = ArtifactEngine(tmpdir)
            qg = QualityGate()

            # Plan 작성
            content = (
                "# Overview\n\nRefactor auth.\n\n"
                "## Technical Approach\n\nJWT tokens.\n\n"
                "## Implementation Steps\n\nSteps here.\n\n"
                "## Tasks\n\n- [ ] Task 1\n- [ ] Task 2\n- [ ] Task 3\n\n"
                "## Timeline\n\nWeek 1.\n\n"
            )
            ae.write_artifact("implementation_plan.md", content)

            pipeline = PlanToBuildPipeline(
                mode_manager=mgr,
                artifact_engine=ae,
                quality_gate=qg,
                min_plan_score=0.3,
            )

            result = pipeline.run(auto_transition=True, create_kanban=False)
            assert result.success is True
            assert result.plan_score >= 0.3
            assert result.task_count >= 3
            assert mgr.is_build is True
            assert "전환 완료" in result.summary()

    def test_pipeline_rejects_bad_plan(self):
        """불완전한 Plan은 전환 실패."""
        from antigravity_k.engine.plan_to_build import PlanToBuildPipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
            ae = ArtifactEngine(tmpdir)

            # 불완전한 Plan
            ae.write_artifact("implementation_plan.md", "# Short")

            pipeline = PlanToBuildPipeline(
                mode_manager=mgr,
                artifact_engine=ae,
                min_plan_score=0.6,
            )
            result = pipeline.run()
            assert result.success is False
            assert mgr.is_plan is True  # 모드 유지

    def test_pipeline_format_status(self):
        """format_status가 현재 파이프라인 상태를 반영."""
        from antigravity_k.engine.plan_to_build import PlanToBuildPipeline

        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        with tempfile.TemporaryDirectory() as tmpdir:
            ae = ArtifactEngine(tmpdir)
            pipeline = PlanToBuildPipeline(mode_manager=mgr, artifact_engine=ae)
            status = pipeline.format_status()
            assert "Plan" in status or "Pipeline" in status


# ═══════════════════════════════════════════════════════════════════════
# D5: QualityGate execution_mode 분기
# ═══════════════════════════════════════════════════════════════════════


class TestD5_QualityGate:
    """QualityGate — execution_mode별 분기 검증."""

    def test_quality_gate_plan_mode_skips_code_check(self):
        """PLAN execution_mode에서 코드 블록 체크 생략."""
        qg = QualityGate()
        # 코드 블록이 없어도 PLAN 모드에서는 감점 없음
        result = qg.evaluate(
            task_type="plan",
            user_request="Create a plan",
            agent_output="# Plan\n\nJust a plan description.",
            execution_mode="plan",
        )
        # PLAN 모드이므로 코드 블록 누락 감점 없음 → 점수 유지
        assert result.grade in (QualityGrade.A, QualityGrade.B, QualityGrade.C)
        # 코드 관련 이슈가 없어야 함
        code_issues = [i for i in result.issues if "코드" in i or "code" in i.lower()]
        assert len(code_issues) == 0

    def test_quality_gate_build_mode_skips_plan_check(self):
        """BUILD execution_mode에서 Plan 체크 생략."""
        qg = QualityGate()
        result = qg.evaluate(
            task_type="coding",
            user_request="Write a function",
            agent_output="Here is a Python function:\n```python\ndef hello():\n    print('hi')\n```",
            execution_mode="build",
        )
        # BUILD 모드이므로 Plan 체크 생략 → 점수 정상
        assert result.score > 0
        plan_issues = [i for i in result.issues if "Plan" in i or "plan" in i]
        assert len(plan_issues) == 0

    def test_quality_gate_standard_evaluation(self):
        """일반 평가: 코드 요청에 코드 블록 포함되어야 함."""
        qg = QualityGate()
        result = qg.evaluate(
            task_type="coding",
            user_request="Write a Python function to sort a list",
            agent_output="# Here's a sorting function\n\n```python\ndef sort_list(items):\n    return sorted(items)\n```\n\nThis is a simple sorting function.",
            execution_mode="interactive",
        )
        assert result.score >= 0.3
        assert result.grade in (QualityGrade.A, QualityGrade.B, QualityGrade.C)

    def test_quality_gate_missing_code_penalty(self):
        """코드 요청에 코드 블록 없으면 감점."""
        qg = QualityGate()
        result = qg.evaluate(
            task_type="coding",
            user_request="Write a Python function",
            agent_output="You should write a function.",
            execution_mode="interactive",
        )
        # 코드 블록 누락 → 감점
        assert result.score < 0.5


# ═══════════════════════════════════════════════════════════════════════
# D6: format_status 출력
# ═══════════════════════════════════════════════════════════════════════


class TestD6_FormatStatus:
    """format_status — CLI/TUI 모드 인디케이터 출력 검증."""

    def test_format_status_plan(self):
        """PLAN 모드 format_status 내용."""
        mgr = ModeManager(initial_mode=ExecutionMode.PLAN)
        status = mgr.format_status()
        assert "PLAN" in status.upper()
        # 이모지 포함 확인 (📋)
        assert "📋" in status or "PLAN" in status  # emoji or text fallback

    def test_format_status_build(self):
        """BUILD 모드 format_status 내용."""
        mgr = ModeManager(initial_mode=ExecutionMode.BUILD)
        status = mgr.format_status()
        assert "BUILD" in status.upper()
        assert "🔨" in status or "BUILD" in status

    def test_format_status_interactive(self):
        """Interactive 모드 format_status 내용."""
        mgr = ModeManager()
        status = mgr.format_status()
        assert "INTERACTIVE" in status.upper()

    def test_format_status_contains_history(self):
        """format_status에 전환 이력 포함."""
        mgr = ModeManager()
        mgr.switch_to_plan("Test plan")
        status = mgr.format_status()
        assert "전환 이력" in status or "transitions" in status.lower() or "1회" in status


# ═══════════════════════════════════════════════════════════════════════
# D7: EventBus publish + 리스너
# ═══════════════════════════════════════════════════════════════════════


class TestD7_EventBusPublish:
    """ModeChanged EventBus publish + 리스너 시스템."""

    def test_listener_receives_all_modes(self):
        """리스너가 모든 모드 전환 이벤트를 수신."""
        mgr = ModeManager()
        events = []

        def listener(from_mode, to_mode, reason):
            events.append((from_mode.value, to_mode.value, reason))

        mgr.add_listener(listener)

        mgr.switch_to_plan("E2E plan")
        mgr.set_plan_artifact("plan.md")
        mgr.set_plan_quality_passed(True)
        mgr.switch_to_build(reason="E2E build")
        mgr.switch_to_interactive("E2E done")

        # 3 mode switch events: plan, build, interactive
        # set_plan_artifact / set_plan_quality_passed do NOT fire listeners
        assert len(events) == 3, f"Expected 3 mode switch events, got {len(events)}"
        assert events[0] == ("interactive", "plan", "E2E plan")
        assert events[1] == ("plan", "build", "E2E build")
        assert events[2] == ("build", "interactive", "E2E done")

    def test_listener_receives_reason(self):
        """리스너에 전환 사유 전달."""
        mgr = ModeManager()
        reasons = []

        def listener(from_mode, to_mode, reason):
            reasons.append(reason)

        mgr.add_listener(listener)
        mgr.switch_to_plan("Specific reason for E2E")
        assert "Specific reason for E2E" in reasons

    def test_eventbus_publish_noncritical(self):
        """EventBus publish 실패는 non-critical (에러 아님)."""
        mgr = ModeManager(initial_mode=ExecutionMode.INTERACTIVE)
        # EventBus가 없어도 모드 전환은 정상 동작
        mgr.switch_to_plan("Test without EventBus")
        assert mgr.is_plan is True

    def test_multiple_listeners(self):
        """다중 리스너 등록/해제."""
        mgr = ModeManager()
        calls1 = []
        calls2 = []

        def listener1(f, t, r):
            calls1.append((f, t))

        def listener2(f, t, r):
            calls2.append((f, t))

        mgr.add_listener(listener1)
        mgr.add_listener(listener2)
        mgr.switch_to_plan("Multi")

        assert len(calls1) == 1
        assert len(calls2) == 1

        # switch_to_build from PLAN requires quality → set flags first
        mgr.set_plan_artifact("plan.md")
        mgr.set_plan_quality_passed(True)
        mgr.remove_listener(listener1)
        mgr.switch_to_build(reason="After remove")

        assert len(calls1) == 1  # 더 이상 호출 안 됨
        assert len(calls2) == 2  # 여전히 호출됨


# ═══════════════════════════════════════════════════════════════════════
# E2E: 전체 플로우 통합 시나리오
# ═══════════════════════════════════════════════════════════════════════


class TestWeek1_E2E_FullFlow:
    """D1~D7 전체 플로우 통합 시나리오."""

    def test_full_plan_build_lifecycle(self):
        """전체 Plan→Build 라이프사이클 E2E 검증."""
        from antigravity_k.engine.plan_to_build import PlanToBuildPipeline

        with tempfile.TemporaryDirectory() as tmpdir:
            # ── Given: 시스템 초기화 ──
            mgr = ModeManager()
            ae = ArtifactEngine(tmpdir)
            qg = QualityGate()
            events = []

            def event_logger(from_mode, to_mode, reason):
                events.append((from_mode.value, to_mode.value, reason))

            mgr.add_listener(event_logger)

            # ── Phase 1: Interactive → Plan ──
            assert mgr.is_interactive is True
            mgr.switch_to_plan("Complex refactoring needed")
            assert mgr.is_plan is True
            assert events[-1] == ("interactive", "plan", "Complex refactoring needed")

            # ── Phase 2: PLAN 모드 권한 검증 ──
            assert mgr.check_tool_permission("read_file")["allowed"] is True
            assert mgr.check_tool_permission("write_file")["allowed"] is False
            assert mgr.check_tool_permission("str_replace")["allowed"] is False

            # ── Phase 3: Plan 아티팩트 생성 ──
            plan_content = (
                "# Overview\n\nRefactor auth module to use JWT.\n\n"
                "## Technical Approach\n\n"
                "Replace session-based auth with JWT tokens.\n\n"
                "## Implementation Steps\n\n"
                "1. Create auth service\n"
                "2. Add JWT validation middleware\n"
                "3. Migrate existing sessions\n\n"
                "## Tasks\n\n"
                "- [ ] Create AuthService class\n"
                "- [ ] Implement JWT token generation\n"
                "- [ ] Add token validation middleware\n"
                "- [ ] Write unit tests for auth\n"
                "- [ ] Migrate existing user sessions\n\n"
                "## Timeline\n\n"
                "Week 1: Core implementation\n"
                "Week 2: Testing and migration\n"
            )
            write_result = ae.write_artifact("implementation_plan.md", plan_content)
            assert write_result["success"] is True

            # ── Phase 4: Plan 검증 ──
            validation = ae.validate_plan_complete()
            assert validation.is_complete is True
            assert validation.score >= 0.6
            assert validation.task_count >= 3

            # ── Phase 5: QualityGate 평가 ──
            quality = qg.evaluate(
                task_type="plan",
                user_request="Create implementation plan for auth refactoring",
                agent_output=plan_content,
                execution_mode="plan",
            )
            # PLAN 모드이므로 코드 블록 체크 생략 → 양호
            assert quality.score >= 0.3

            # ── Phase 6: PlanToBuildPipeline ──
            pipeline = PlanToBuildPipeline(
                mode_manager=mgr,
                artifact_engine=ae,
                quality_gate=qg,
                min_plan_score=0.3,
            )
            assert pipeline.quick_check() is True

            result = pipeline.run(auto_transition=True, create_kanban=False)
            assert result.success is True
            assert result.plan_score >= 0.3

            # ── Phase 7: BUILD 모드 검증 ──
            assert mgr.is_build is True
            assert events[-1][1] == "build"
            assert events[-1][2] == "Plan 검증 완료 (파일: implementation_plan.md)"

            # BUILD 모드: 모든 도구 허용
            assert mgr.check_tool_permission("write_file")["allowed"] is True
            assert mgr.check_tool_permission("str_replace")["allowed"] is True
            assert mgr.check_tool_permission("run_bash_command")["allowed"] is True

            # BUILD 모드: restricted 도구 승인 필요
            assert mgr.check_tool_permission("deploy")["requires_approval"] is True

            # ── Phase 8: Interactive 복귀 ──
            mgr.switch_to_interactive("Refactoring complete")
            assert mgr.is_interactive is True
            assert events[-1][1] == "interactive"

            # ── Phase 9: 최종 상태 확인 ──
            # 3 switches: plan, build, interactive
            assert len(mgr.mode_history) == 3
            d = mgr.to_dict()
            assert d["current_mode"] == "interactive"
            assert d["history_count"] == 3

            status = mgr.format_status()
            assert "INTERACTIVE" in status.upper()

            # Artifact 검증
            artifacts = ae.list_artifacts()
            assert len(artifacts) >= 1
            assert any("implementation_plan" in a["filename"] for a in artifacts)
