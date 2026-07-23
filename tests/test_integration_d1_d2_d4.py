"""Phase 1 D1/D2/D4 통합 E2E 테스트.

ModeManager (D1) + ArtifactEngine (D2) + PlanToBuildPipeline (D4)의
전체 워크플로우를 end-to-end로 검증합니다.

테스트 시나리오:
  1. 단일 컴포넌트 단위 테스트
  2. 통합 E2E 시나리오 (Plan 작성 → 검증 → Build 전환)
  3. 엣지 케이스 (파일 없음, 점수 미달, 중복 전환)
"""

import os
import tempfile

import pytest

from antigravity_k.engine.artifact_engine import (
    ArtifactEngine,
    ArtifactMetadata,
    PlanTask,
)
from antigravity_k.engine.execution_mode import ExecutionMode
from antigravity_k.engine.mode_manager import ModeManager
from antigravity_k.engine.plan_to_build import (
    PlanToBuildPipeline,
    TransitionPhase,
    TransitionResult,
)
from antigravity_k.engine.quality_gate import QualityGate

# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def project_root():
    """임시 프로젝트 루트 디렉토리."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield tmpdir


@pytest.fixture
def mode_manager():
    """ModeManager 인스턴스 (기본값: INTERACTIVE)."""
    return ModeManager(initial_mode=ExecutionMode.INTERACTIVE)


@pytest.fixture
def artifact_engine(project_root):
    """ArtifactEngine 인스턴스 (임시 디렉토리 기반)."""
    return ArtifactEngine(project_root)


@pytest.fixture
def quality_gate():
    """QualityGate 인스턴스."""
    return QualityGate()


@pytest.fixture
def pipeline(mode_manager, artifact_engine, quality_gate):
    """PlanToBuildPipeline 인스턴스."""
    return PlanToBuildPipeline(
        mode_manager=mode_manager,
        artifact_engine=artifact_engine,
        quality_gate=quality_gate,
    )


@pytest.fixture
def valid_plan_content():
    """완전한 Plan 마크다운 콘텐츠 (5개 필수 섹션 포함, 체크박스 3개 이상, 200자 이상)."""
    return """# Implementation Plan: Example Feature

## Overview
이 프로젝트는 예시 기능을 구현합니다. 주요 목표는 사용자 인증 시스템을 구축하는 것입니다.

## Technical Approach
다음과 같은 기술 접근 방식을 사용합니다:
- FastAPI 기반 REST API
- JWT 토큰 인증
- PostgreSQL 데이터베이스
- Redis 캐싱

## Implementation Steps
1. 데이터베이스 스키마 설계
2. 인증 미들웨어 구현
3. API 엔드포인트 개발
4. 테스트 작성

## Task List
- [ ] P0: 데이터베이스 스키마 설계 — users, sessions 테이블 생성
- [ ] P1: JWT 인증 미들웨어 구현 — `auth/middleware.py`
- [ ] 🔴 Redis 캐싱 통합 — `cache/session.py` depends: middleware
- [x] 프로젝트 초기 설정 완료

## Timeline / Priority
- Phase 1: 1-2일 (인증 기반)
- Phase 2: 3-4일 (캐싱 및 최적화)
- 우선순위: P0(데이터베이스) > P1(인증) > P2(캐싱)
"""


@pytest.fixture
def incomplete_plan_content():
    """불완전한 Plan (섹션 누락, 체크박스 없음, 200자 미만)."""
    return "# Quick Note\n\nSome brief thoughts."


# =========================================================================
# D1: ModeManager 단위 테스트
# =========================================================================


class TestModeManager:
    """ModeManager 기본 동작 검증 (D1)."""

    def test_initial_mode(self, mode_manager):
        """초기 모드는 INTERACTIVE여야 함."""
        assert mode_manager.current_mode == ExecutionMode.INTERACTIVE
        assert mode_manager.is_interactive is True
        assert mode_manager.is_plan is False
        assert mode_manager.is_build is False

    def test_switch_to_plan(self, mode_manager):
        """Plan 모드 전환."""
        result = mode_manager.switch_to_plan(reason="테스트 필요")
        assert result is True
        assert mode_manager.current_mode == ExecutionMode.PLAN
        assert mode_manager.is_plan is True
        assert mode_manager.is_interactive is False

    def test_switch_to_build_requires_quality(self, mode_manager):
        """Plan→Build 전환은 QualityGate 통과가 필요함."""
        mode_manager.switch_to_plan(reason="Plan 수립")
        result = mode_manager.switch_to_build(reason="Build 전환")
        assert result is False  # QualityGate 통과 전이므로 실패
        assert mode_manager.is_plan is True  # PLAN 유지

    def test_switch_to_build_success(self, mode_manager):
        """Plan→Build 전환 성공 조건 충족 후 전환."""
        mode_manager.switch_to_plan(reason="Plan 수립")
        mode_manager.set_plan_quality_passed(True)
        mode_manager.set_plan_artifact("artifacts/implementation_plan.md")

        assert mode_manager.can_auto_transition_to_build is True

        result = mode_manager.switch_to_build(
            plan_artifact_path="artifacts/implementation_plan.md",
            reason="Plan 검증 완료",
        )
        assert result is True
        assert mode_manager.current_mode == ExecutionMode.BUILD
        assert mode_manager.is_build is True

    def test_switch_to_interactive(self, mode_manager):
        """Interactive 모드 전환."""
        mode_manager.switch_to_plan(reason="Plan")
        mode_manager.switch_to_interactive(reason="대화형 복귀")
        assert mode_manager.current_mode == ExecutionMode.INTERACTIVE
        assert mode_manager.is_interactive is True

    def test_idempotent_switch(self, mode_manager):
        """동일 모드로의 중복 전환은 무시되어야 함."""
        assert mode_manager.switch_to_interactive(reason="test") is True
        # 상태가 변경되지 않아도 성공 반환

    def test_mode_history(self, mode_manager):
        """모드 전환 이력이 정확히 기록되어야 함."""
        mode_manager.switch_to_plan(reason="Reason 1")
        mode_manager.set_plan_quality_passed(True)
        mode_manager.switch_to_build(reason="Reason 2")
        mode_manager.switch_to_interactive(reason="Reason 3")

        history = mode_manager.mode_history
        assert len(history) == 3
        assert history[0].from_mode == "interactive"
        assert history[0].to_mode == "plan"
        assert history[0].reason == "Reason 1"
        assert history[1].to_mode == "build"
        assert history[1].reason == "Reason 2"
        assert history[2].to_mode == "interactive"
        assert history[2].reason == "Reason 3"

    def test_tool_permission_plan_mode(self, mode_manager):
        """PLAN 모드에서 읽기 전용 도구 허용, 쓰기 도구 차단."""
        mode_manager.switch_to_plan(reason="test")

        # 읽기 전용 도구 허용
        read_perm = mode_manager.check_tool_permission("read_file")
        assert read_perm["allowed"] is True

        # 쓰기 도구 차단
        write_perm = mode_manager.check_tool_permission("write_file")
        assert write_perm["allowed"] is False
        assert "PLAN MODE" in write_perm["reason"]

        # write_artifact는 PLAN 모드에서 허용
        artifact_perm = mode_manager.check_tool_permission("write_artifact")
        assert artifact_perm["allowed"] is True

    def test_tool_permission_build_mode(self, mode_manager):
        """BUILD 모드에서 모든 도구 허용."""
        mode_manager.switch_to_plan(reason="plan")
        mode_manager.set_plan_quality_passed(True)
        mode_manager.switch_to_build(reason="build")

        write_perm = mode_manager.check_tool_permission("write_file")
        assert write_perm["allowed"] is True

        # restricted 도구는 approval 필요
        deploy_perm = mode_manager.check_tool_permission("deploy")
        assert deploy_perm["allowed"] is True
        assert deploy_perm["requires_approval"] is True

    def test_auto_transition_property(self, mode_manager):
        """can_auto_transition_to_build 속성 정확성."""
        assert mode_manager.can_auto_transition_to_build is False

        mode_manager.set_plan_artifact("plan.md")
        assert mode_manager.can_auto_transition_to_build is False  # quality 아직

        mode_manager.set_plan_quality_passed(True)
        assert mode_manager.can_auto_transition_to_build is True

    def test_should_enforce_plan_mode(self, mode_manager):
        """복잡한 태스크에서 Plan 모드 강제 판단."""
        assert mode_manager.should_enforce_plan_mode("complex", "") is True
        assert mode_manager.should_enforce_plan_mode("coding", "리팩토링 필요") is True
        assert mode_manager.should_enforce_plan_mode("coding", "간단한 버그 수정") is False
        assert mode_manager.should_enforce_plan_mode("simple", "") is False

        # 이미 PLAN 모드면 강제하지 않음
        mode_manager.switch_to_plan(reason="test")
        assert mode_manager.should_enforce_plan_mode("complex", "") is False

    def test_to_dict(self, mode_manager):
        """to_dict() 상태 직렬화."""
        mode_manager.switch_to_plan(reason="test")
        state = mode_manager.to_dict()
        assert state["current_mode"] == "plan"
        assert state["is_plan"] is True
        assert state["auto_transition_enabled"] is True
        assert state["history_count"] == 1
        assert state["last_transition"]["to"] == "plan"

    def test_format_status(self, mode_manager):
        """format_status() 출력."""
        mode_manager.switch_to_plan(reason="분석 필요")
        status = mode_manager.format_status()
        assert "PLAN" in status or "plan" in status
        assert "분석 필요" in status

    def test_mode_change_listener(self, mode_manager):
        """모드 변경 리스너 호출."""
        changes = []

        def listener(from_mode, to_mode, reason):
            changes.append((from_mode.value, to_mode.value, reason))

        mode_manager.add_listener(listener)
        mode_manager.switch_to_plan(reason="listener test")
        assert len(changes) == 1
        assert changes[0] == ("interactive", "plan", "listener test")

        # 리스너 제거
        mode_manager.remove_listener(listener)
        mode_manager.switch_to_interactive(reason="after remove")
        assert len(changes) == 1  # 변경 없음


# =========================================================================
# D2: ArtifactEngine 단위 테스트
# =========================================================================


class TestArtifactEngine:
    """ArtifactEngine 기본 동작 검증 (D2)."""

    def test_artifacts_dir_created(self, artifact_engine):
        """artifacts/ 디렉토리가 자동 생성되어야 함."""
        assert os.path.exists(artifact_engine.artifacts_dir)

    def test_write_and_read_artifact(self, artifact_engine):
        """아티팩트 쓰기 및 읽기."""
        content = "# Test Plan\n\nSimple plan content."
        result = artifact_engine.write_artifact("test_plan.md", content)
        assert result["success"] is True
        assert "test_plan" in result["filepath"]

        read_back = artifact_engine.read_artifact("test_plan.md")
        assert read_back == content

    def test_write_artifact_with_metadata(self, artifact_engine):
        """메타데이터와 함께 아티팩트 작성."""
        metadata = ArtifactMetadata(
            artifact_type="implementation_plan",
            summary="Test plan",
            request_feedback=True,
        )
        result = artifact_engine.write_artifact(
            "implementation_plan.md",
            "# Plan",
            metadata=metadata,
        )
        assert result["success"] is True
        assert result["request_feedback"] is True

    def test_read_nonexistent_artifact(self, artifact_engine):
        """존재하지 않는 아티팩트 읽기 → None."""
        result = artifact_engine.read_artifact("nonexistent.md")
        assert result is None

    def test_delete_artifact(self, artifact_engine):
        """아티팩트 삭제."""
        artifact_engine.write_artifact("to_delete.md", "# Delete me")
        assert artifact_engine.delete_artifact("to_delete.md") is True
        assert artifact_engine.read_artifact("to_delete.md") is None

    def test_delete_nonexistent_artifact(self, artifact_engine):
        """존재하지 않는 아티팩트 삭제 → False."""
        assert artifact_engine.delete_artifact("nonexistent.md") is False

    def test_list_artifacts(self, artifact_engine):
        """아티팩트 목록 조회."""
        artifact_engine.write_artifact("plan_a.md", "# Plan A")
        artifact_engine.write_artifact("plan_b.md", "# Plan B")
        artifact_engine.write_artifact("task.md", "# Tasks")
        artifact_engine.write_artifact("note.txt", "# This won't appear")  # .md 아님

        artifacts = artifact_engine.list_artifacts()
        # .md 파일만 반환
        filenames = [a["filename"] for a in artifacts]
        assert "plan_a.md" in filenames
        assert "plan_b.md" in filenames
        assert "task.md" in filenames
        assert "note.txt" not in filenames

        # 유형 분류 확인
        plan_types = [a for a in artifacts if a["type"] == "implementation_plan"]
        assert len(plan_types) == 2

    # ─── validate_plan_complete ──────────────────────────────────

    def test_validate_complete_plan(self, artifact_engine, valid_plan_content):
        """완전한 Plan 검증 → score >= 0.6, is_complete=True."""
        artifact_engine.write_artifact("implementation_plan.md", valid_plan_content)
        result = artifact_engine.validate_plan_complete()

        assert result.is_complete is True
        assert result.score >= 0.6
        assert len(result.missing_sections) == 0
        assert result.task_count >= 3  # 체크박스 4개

    def test_validate_missing_plan(self, artifact_engine):
        """존재하지 않는 Plan 검증 → score 0.0, is_complete=False."""
        result = artifact_engine.validate_plan_complete("nonexistent.md")
        assert result.is_complete is False
        assert result.score == 0.0
        assert "(artifact not found)" in result.missing_sections

    def test_validate_incomplete_plan(self, artifact_engine, incomplete_plan_content):
        """불완전한 Plan 검증 → is_complete=False."""
        artifact_engine.write_artifact("implementation_plan.md", incomplete_plan_content)
        result = artifact_engine.validate_plan_complete()

        assert result.is_complete is False
        assert result.score < 0.6
        assert len(result.missing_sections) > 0
        assert result.task_count == 0

    def test_validate_plan_with_partial_sections(self, artifact_engine):
        """일부 섹션만 있는 Plan → 누락 섹션이 1개 이하여도 점수 미달 가능."""
        content = """# Overview
This is an overview section with enough text to meet minimum length requirements.

## Technical Approach
Using Python and FastAPI with proper architecture patterns.

## Implementation Steps
Step 1: Do something
Step 2: Do something else

（No task list or timeline section here — these should be detected as missing）
"""
        artifact_engine.write_artifact("implementation_plan.md", content)
        result = artifact_engine.validate_plan_complete()

        # Task List(Task List 패턴 체크박스)와 Timeline 섹션이 누락되거나 체크박스가 없어 점수 감점
        assert result.score < 1.0
        # 체크박스가 없으므로 task_count 0
        assert result.task_count == 0

    def test_is_plan_ready_for_build(self, artifact_engine, valid_plan_content):
        """is_plan_ready_for_build() 편의 메서드."""
        # 완전한 Plan
        artifact_engine.write_artifact("implementation_plan.md", valid_plan_content)
        assert artifact_engine.is_plan_ready_for_build() is True

        # 불완전한 Plan
        artifact_engine.write_artifact("implementation_plan.md", "# Short")
        assert artifact_engine.is_plan_ready_for_build() is False

    # ─── extract_plan_tasks ──────────────────────────────────────

    def test_extract_tasks(self, artifact_engine, valid_plan_content):
        """Plan에서 태스크 추출."""
        artifact_engine.write_artifact("implementation_plan.md", valid_plan_content)
        tasks = artifact_engine.extract_plan_tasks()

        assert len(tasks) >= 3  # 최소 3개 태스크
        assert all(isinstance(t, PlanTask) for t in tasks)

    def test_extract_tasks_priority_detection(self, artifact_engine, valid_plan_content):
        """태스크 우선순위 감지 (P0, P1, 🔴)."""
        artifact_engine.write_artifact("implementation_plan.md", valid_plan_content)
        tasks = artifact_engine.extract_plan_tasks()

        # P0 태스크는 priority 2
        p0_tasks = [t for t in tasks if t.priority >= 2]
        assert len(p0_tasks) >= 1  # P0: 데이터베이스 스키마 + 🔴 Redis 캐싱

        # P1 태스크는 priority 1
        p1_tasks = [t for t in tasks if t.priority == 1]
        assert len(p1_tasks) >= 1

    def test_extract_tasks_section_grouping(self, artifact_engine, valid_plan_content):
        """태스크가 섹션별로 그룹화되어야 함."""
        artifact_engine.write_artifact("implementation_plan.md", valid_plan_content)
        tasks = artifact_engine.extract_plan_tasks()

        sections = {t.section for t in tasks}
        assert "Task List" in sections or any("Task" in s for s in sections)

    def test_extract_tasks_no_plan(self, artifact_engine):
        """Plan이 없으면 빈 리스트 반환."""
        tasks = artifact_engine.extract_plan_tasks("nonexistent.md")
        assert tasks == []

    def test_extract_tasks_no_checkboxes(self, artifact_engine):
        """체크박스가 없으면 빈 리스트 반환."""
        artifact_engine.write_artifact("plan.md", "# Overview\n\nJust text without checkboxes.")
        tasks = artifact_engine.extract_plan_tasks("plan.md")
        assert tasks == []

    # ─── auto_create_kanban_tasks ────────────────────────────────

    def test_auto_create_kanban_tasks_graceful_skip(self, artifact_engine, valid_plan_content):
        """KanbanEngine 없이도 graceful skip (ImportError → 실패가 아니라 메시지 반환)."""
        artifact_engine.write_artifact("implementation_plan.md", valid_plan_content)
        result = artifact_engine.auto_create_kanban_tasks()

        # KanbanEngine이 없으면 success=False지만 task_count는 있음
        if result["success"] is False:
            assert "KanbanEngine" in result["message"] or "task_count" in result
        else:
            # KanbanEngine이 있으면 success=True
            assert result["success"] is True
            assert result["task_count"] > 0

    # ─── summarize_plan ──────────────────────────────────────────

    def test_summarize_plan(self, artifact_engine, valid_plan_content):
        """Plan 요약 리포트."""
        artifact_engine.write_artifact("implementation_plan.md", valid_plan_content)
        summary = artifact_engine.summarize_plan()

        assert "Plan Summary" in summary
        assert "Validation" in summary
        assert "Tasks" in summary

    def test_summarize_missing_plan(self, artifact_engine):
        """없는 Plan 요약."""
        summary = artifact_engine.summarize_plan("nonexistent.md")
        assert "Plan Summary" in summary

    # ─── inject_planning_prompt ──────────────────────────────────

    def test_inject_planning_prompt(self, artifact_engine):
        """Planning Prompt에 필수 섹션과 QualityGate 조건이 포함되어야 함."""
        prompt = artifact_engine.inject_planning_prompt()
        assert "PLANNING MODE" in prompt
        assert "write_artifact" in prompt
        assert "implementation_plan" in prompt
        assert "QualityGate" in prompt
        assert "BUILD MODE" in prompt


# =========================================================================
# D4: PlanToBuildPipeline 단위 테스트
# =========================================================================


class TestPlanToBuildPipeline:
    """PlanToBuildPipeline 기본 동작 검증 (D4)."""

    def test_pipeline_missing_mode_manager(self, artifact_engine):
        """ModeManager 없이 실행 → errors 포함."""
        pipeline = PlanToBuildPipeline(mode_manager=None, artifact_engine=artifact_engine)
        result = pipeline.run()
        assert result.success is False
        assert any("ModeManager" in e for e in result.errors)

    def test_pipeline_missing_artifact_engine(self, mode_manager):
        """ArtifactEngine 없이 실행 → errors 포함."""
        pipeline = PlanToBuildPipeline(mode_manager=mode_manager, artifact_engine=None)
        result = pipeline.run()
        assert result.success is False
        assert any("ArtifactEngine" in e for e in result.errors)

    def test_pipeline_no_plan_file(self, pipeline):
        """Plan 파일 없이 실행 → 실패 (파일 없음 오류)."""
        pipeline.mode_manager.switch_to_plan(reason="test")
        result = pipeline.run(plan_file="nonexistent.md")
        assert result.success is False
        assert result.plan_score == 0.0

    def test_pipeline_successful_transition(self, pipeline, artifact_engine, mode_manager, valid_plan_content):
        """완전한 Plan → 전체 파이프라인 성공 + Build 전환."""
        # 1. PLAN 모드로 전환
        mode_manager.switch_to_plan(reason="E2E 테스트")

        # 2. Plan 아티팩트 작성
        artifact_engine.write_artifact("implementation_plan.md", valid_plan_content)

        # 3. 파이프라인 실행
        result = pipeline.run()

        # 4. 검증
        assert result.success is True, f"Pipeline failed: {result.errors}"
        assert result.plan_score >= 0.6
        assert result.task_count >= 3
        assert len(result.steps) == 4  # validate + quality + transition + kanban

        # 5. Build 모드로 전환되었는지 확인
        assert mode_manager.current_mode == ExecutionMode.BUILD
        assert mode_manager.is_build is True

        # 6. 각 단계별 성공 확인
        for step in result.steps:
            assert step.success, f"Step {step.phase} failed: {step.message}"

        # 7. Plan 아티팩트 경로 설정 확인
        assert mode_manager.plan_artifact_path is not None
        assert "implementation_plan.md" in mode_manager.plan_artifact_path

    def test_pipeline_without_auto_transition(self, pipeline, artifact_engine, mode_manager, valid_plan_content):
        """auto_transition=False → 검증만 하고 전환은 하지 않음."""
        mode_manager.switch_to_plan(reason="test")
        artifact_engine.write_artifact("implementation_plan.md", valid_plan_content)

        result = pipeline.run(auto_transition=False)

        assert result.success is True
        assert result.plan_score >= 0.6
        # 4개 스텝 중 transition 스텝이 없어야 함 (auto_transition=False)
        step_phases = [s.phase for s in result.steps]
        assert TransitionPhase.MODE_TRANSITION not in step_phases

        # 모드가 PLAN으로 유지되어야 함
        assert mode_manager.is_plan is True

    def test_pipeline_without_kanban(self, pipeline, artifact_engine, mode_manager, valid_plan_content):
        """create_kanban=False → Kanban 생성 스텝 생략."""
        mode_manager.switch_to_plan(reason="test")
        artifact_engine.write_artifact("implementation_plan.md", valid_plan_content)

        result = pipeline.run(create_kanban=False)

        assert result.success is True
        step_phases = [s.phase for s in result.steps]
        assert TransitionPhase.KANBAN_CREATION not in step_phases

    def test_pipeline_incomplete_plan(self, pipeline, artifact_engine, mode_manager, incomplete_plan_content):
        """불완전한 Plan → 실패, BUILD 전환 안 됨."""
        mode_manager.switch_to_plan(reason="test")
        artifact_engine.write_artifact("implementation_plan.md", incomplete_plan_content)

        result = pipeline.run()

        assert result.success is False
        assert result.plan_score < 0.6
        assert mode_manager.is_plan is True  # PLAN 유지
        assert mode_manager.is_build is False

    def test_quick_check(self, pipeline, artifact_engine, valid_plan_content):
        """quick_check() — 전환 없이 검증만."""
        artifact_engine.write_artifact("implementation_plan.md", valid_plan_content)

        # pipeline의 mode_manager가 설정되어 있어야 함
        assert pipeline.quick_check() is True

        # 불완전한 Plan
        artifact_engine.write_artifact("implementation_plan.md", "# Short")
        # artifact_engine.write_artifact에서 파일명이 같으면 덮어쓰기됨
        assert pipeline.quick_check() is False

    def test_quick_check_no_artifact_engine(self, mode_manager):
        """quick_check() — ArtifactEngine 없으면 False."""
        pipeline = PlanToBuildPipeline(mode_manager=mode_manager, artifact_engine=None)
        assert pipeline.quick_check() is False

    def test_format_status(self, pipeline, mode_manager):
        """format_status() — 파이프라인 상태 출력."""
        status = pipeline.format_status()
        assert "Pipeline Status" in status

        mode_manager.switch_to_plan(reason="test")
        status = pipeline.format_status()
        assert "PLAN" in status or "plan" in status

    def test_transition_result_summary(self):
        """TransitionResult.summary() 포맷."""
        # 성공 케이스
        success_result = TransitionResult(
            success=True,
            plan_file="implementation_plan.md",
            plan_score=0.85,
            task_count=5,
            kanban_task_count=3,
        )
        summary = success_result.summary()
        assert "✅" in summary
        assert "85%" in summary or "0.85" in summary

        # 실패 케이스
        fail_result = TransitionResult(
            success=False,
            errors=["Plan 점수 0.3이 최소 기준 0.6 미만"],
        )
        summary = fail_result.summary()
        assert "❌" in summary
        assert "점수" in summary


# =========================================================================
# E2E 통합 시나리오
# =========================================================================


class TestIntegrationE2E:
    """전체 E2E 통합 시나리오: D1 → D2 → D4 워크플로우."""

    def test_full_e2e_workflow(self, pipeline, artifact_engine, mode_manager, valid_plan_content):
        """전체 워크플로우: Interactive → Plan 작성 → 검증 → Build 전환."""
        # ─── Phase 1: 초기 상태 ───
        assert mode_manager.current_mode == ExecutionMode.INTERACTIVE
        assert mode_manager.is_interactive is True

        # ─── Phase 2: Plan 모드 전환 ───
        mode_manager.switch_to_plan(reason="새 기능 구현 계획 수립")
        assert mode_manager.is_plan is True
        assert mode_manager.plan_artifact_path is None
        assert mode_manager.can_auto_transition_to_build is False

        # ─── Phase 3: Plan 아티팩트 작성 ───
        write_result = artifact_engine.write_artifact(
            "implementation_plan.md",
            valid_plan_content,
            metadata=ArtifactMetadata(
                artifact_type="implementation_plan",
                summary="예시 기능 구현 Plan",
                request_feedback=False,
            ),
        )
        assert write_result["success"] is True

        # 아티팩트 읽기 확인
        content = artifact_engine.read_artifact("implementation_plan.md")
        assert content is not None
        assert "Implementation Plan" in content

        # ─── Phase 4: Plan 검증 ───
        validation = artifact_engine.validate_plan_complete()
        assert validation.is_complete is True
        assert validation.score >= 0.6
        assert len(validation.missing_sections) == 0
        assert validation.task_count >= 3

        # 태스크 추출
        tasks = artifact_engine.extract_plan_tasks()
        assert len(tasks) >= 3
        # 완료된 태스크 (✔) 와 미완료 태스크 구분
        todo_tasks = [t for t in tasks if t.status == "todo"]
        assert len(todo_tasks) >= 2

        # 아티팩트 목록 조회
        artifacts = artifact_engine.list_artifacts()
        assert len(artifacts) >= 1
        plan_artifacts = [a for a in artifacts if a["type"] == "implementation_plan"]
        assert len(plan_artifacts) >= 1

        # ─── Phase 5: Plan→Build 파이프라인 실행 ───
        result = pipeline.run()

        assert result.success is True
        assert result.plan_score >= 0.6
        assert result.task_count >= 3
        assert len(result.steps) == 4

        # 각 단계 검증
        step_details = {s.phase: s for s in result.steps}
        assert step_details[TransitionPhase.PLAN_VALIDATION].success is True
        assert step_details[TransitionPhase.MODE_TRANSITION].success is True

        # ─── Phase 6: Build 모드 확인 ───
        assert mode_manager.is_build is True
        assert mode_manager.current_mode == ExecutionMode.BUILD
        assert mode_manager.plan_artifact_path is not None
        assert mode_manager.can_auto_transition_to_build is True

        # Build 모드에서 도구 권한 확인
        write_perm = mode_manager.check_tool_permission("write_file")
        assert write_perm["allowed"] is True

        # ─── Phase 7: 모드 이력 확인 ───
        history = mode_manager.mode_history
        assert len(history) >= 2
        assert history[0].to_mode == "plan"
        assert history[-1].to_mode == "build"

        # ─── Phase 8: Interactive 복귀 ───
        mode_manager.switch_to_interactive(reason="작업 완료")
        assert mode_manager.is_interactive is True
        # Plan 정보 초기화 확인
        # switch_to_interactive에서 _plan_artifact_path와 _plan_quality_passed가 초기화됨
        assert mode_manager.plan_artifact_path is None

    def test_e2e_failed_scenario(self, pipeline, artifact_engine, mode_manager, incomplete_plan_content):
        """실패 시나리오: 불완전한 Plan → 파이프라인 실패 → Interactive 복귀."""
        # Interactive → Plan
        mode_manager.switch_to_plan(reason="테스트")
        assert mode_manager.is_plan is True

        # 불완전한 Plan 작성
        artifact_engine.write_artifact("implementation_plan.md", incomplete_plan_content)

        # 검증 실패 확인
        validation = artifact_engine.validate_plan_complete()
        assert validation.is_complete is False
        assert validation.score < 0.6

        # 파이프라인 실패 확인
        result = pipeline.run()
        assert result.success is False
        assert result.plan_score < 0.6

        # 모드가 PLAN으로 유지됨 (BUILD로 전환되지 않음)
        assert mode_manager.is_plan is True
        assert mode_manager.is_build is False

        # Interactive 복귀
        mode_manager.switch_to_interactive(reason="실패")
        assert mode_manager.is_interactive is True
