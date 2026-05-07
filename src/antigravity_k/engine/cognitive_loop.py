"""
Antigravity-K: 인지 루프 엔진 (CognitiveLoop)
==============================================
E-1: AI 에이전트의 사고 패턴을 구현합니다.

현재 Antigravity-K: CEO 분류 → 에이전트 실행 → 끝 (1-pass)
개선 후:          Plan → Execute → Verify → Reflect → Adapt (순환)

이 모듈은 에이전트가 "생각하고 → 실행하고 → 검증하고 → 배우는"
인간 전문가의 인지 패턴을 에뮬레이트합니다.
"""

import ast
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class PlanStep:
    """실행 계획의 단일 단계."""

    step_id: int
    description: str
    tool: Optional[str] = None
    args: Optional[Dict[str, Any]] = None
    status: str = "pending"  # pending, running, done, failed, skipped
    result: Optional[str] = None
    verification: Optional[str] = None  # 검증 결과


@dataclass
class ExecutionPlan:
    """에이전트의 실행 계획."""

    goal: str
    steps: List[PlanStep] = field(default_factory=list)
    created_at: str = ""
    confidence: str = "medium"  # high, medium, low
    reasoning: str = ""


@dataclass
class ReflectionResult:
    """작업 완료 후 성찰 결과."""

    what_worked: List[str] = field(default_factory=list)
    what_failed: List[str] = field(default_factory=list)
    lessons: List[str] = field(default_factory=list)
    should_retry: bool = False
    retry_strategy: str = ""


class CognitiveLoop:
    """
    Plan → Execute → Verify → Reflect → Adapt 인지 순환 엔진.

    Orchestrator의 _run_single_agent() 내부에서 사용되어,
    각 도구 실행 후 자동 검증 및 실패 시 전략 변경을 수행합니다.

    사용자 이익 원칙:
    - 검증 실패 시 자동으로 다른 접근법 시도
    - 반복 실패 시 사용자에게 솔직하게 보고
    - 모든 학습 내용을 영속적으로 저장
    """

    def __init__(
        self, project_root: str = ".", failure_memory=None, external_brain_router=None
    ):
        self.project_root = project_root
        self.failure_memory = failure_memory
        self._external_brain_router = external_brain_router
        self._current_plan: Optional[ExecutionPlan] = None
        self._step_history: List[Dict[str, Any]] = []
        self._retry_count = 0
        self._max_retries = 2
        self._dialectic_enabled = True  # 변증법적 자기 비판 활성화 (Hegelion 패턴)

    # ─── Phase 1: PLAN ─────────────────────────────────────

    def create_plan_prompt(self, task: str, available_tools: List[str]) -> str:
        """에이전트에게 계획을 세우도록 하는 프롬프트를 생성합니다."""
        failure_context = ""
        if self.failure_memory:
            similar = self.failure_memory.find_similar(task)
            if similar:
                failure_context = (
                    "\n\n⚠️ 과거 유사 작업에서의 실패 기록:\n"
                    + "\n".join(
                        f"- {f['error_pattern']}: {f['fix_applied']}"
                        for f in similar[:3]
                    )
                    + "\n위 실수를 반복하지 마세요.\n"
                )

        return (
            "<scratch_pad>\n"
            f"Goal: {task}\n"
            f"Available Tools: {', '.join(available_tools[:20])}\n"
            f"{failure_context}"
            "Actions: 먼저 아래 형식으로 실행 계획을 세우세요:\n"
            "1. [단계 설명] — 사용할 도구\n"
            "2. [단계 설명] — 사용할 도구\n"
            "...\n"
            "Observation: None (아직 실행 전)\n"
            "Reflection: 이 계획이 목표를 달성하기에 충분한지 자가 검증하세요.\n"
            "</scratch_pad>"
        )

    # ─── Phase 2: VERIFY ─────────────────────────────────────

    def verify_tool_result(
        self, tool_name: str, tool_args: Dict, result: str
    ) -> Dict[str, Any]:
        """
        도구 실행 결과를 자동 검증합니다.

        Returns:
            {
                "passed": bool,
                "grade": "A" | "B" | "C" | "F",
                "issues": [...],
                "suggestion": "..."
            }
        """
        issues = []
        grade = "A"

        # 에러 감지
        if isinstance(result, str):
            result_lower = result.lower()

            # 명시적 에러
            if result.strip().startswith("Error") or result.strip().startswith(
                "There was an error"
            ):
                grade = "F"
                issues.append(f"도구 '{tool_name}'이 에러를 반환했습니다")

            # 파일 관련 도구: 파일 존재 여부 확인
            file_path = tool_args.get("file_path") or tool_args.get("path", "")
            if tool_name in ("write_file", "edit_file", "replace_file_content"):
                if file_path and not os.path.exists(file_path):
                    # 상대 경로면 프로젝트 루트 기준
                    abs_path = os.path.join(self.project_root, file_path)
                    if not os.path.exists(abs_path):
                        grade = "C"
                        issues.append(
                            f"파일이 생성/수정되었으나 확인할 수 없음: {file_path}"
                        )

            # 코드 생성 도구: AST 검증
            if (
                tool_name in ("write_file", "edit_file")
                and file_path
                and file_path.endswith(".py")
            ):
                try:
                    actual_path = (
                        file_path
                        if os.path.exists(file_path)
                        else os.path.join(self.project_root, file_path)
                    )
                    if os.path.exists(actual_path):
                        with open(actual_path, "r", encoding="utf-8") as f:
                            ast.parse(f.read())
                except SyntaxError as e:
                    grade = "F"
                    issues.append(f"생성된 Python 코드에 구문 오류: {e}")

            # bash 명령: exit code 확인
            if tool_name == "run_bash_command":
                if "command not found" in result_lower:
                    grade = "C"
                    issues.append("명령어를 찾을 수 없음")
                elif "permission denied" in result_lower:
                    grade = "C"
                    issues.append("권한 거부됨")
                elif "traceback" in result_lower or "error:" in result_lower:
                    grade = "C"
                    issues.append("명령 실행 중 에러 발생")

            # 빈 결과
            if not result.strip():
                grade = "C"
                issues.append("도구가 빈 결과를 반환했습니다")

        passed = grade in ("A", "B")

        # 실패 시 제안
        suggestion = ""
        if not passed:
            suggestion = self._suggest_fix(tool_name, tool_args, result, issues)

        # 이력 기록
        self._step_history.append(
            {
                "tool": tool_name,
                "grade": grade,
                "passed": passed,
                "issues": issues,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return {
            "passed": passed,
            "grade": grade,
            "issues": issues,
            "suggestion": suggestion,
            "dialectic_applied": not passed and self._dialectic_enabled,
        }

    def _suggest_fix(
        self, tool_name: str, args: Dict, result: str, issues: List[str]
    ) -> str:
        """검증 실패 시 수정 제안을 생성합니다."""
        if "구문 오류" in str(issues):
            return "코드를 다시 검토하고, 들여쓰기와 괄호 매칭을 확인하세요."
        if "찾을 수 없음" in str(issues):
            return "명령어 또는 패키지가 설치되어 있는지 확인하세요."
        if "권한 거부" in str(issues):
            return "sudo를 사용하거나 파일 권한을 확인하세요."
        if "에러를 반환" in str(issues):
            return "에러 메시지를 분석하고 다른 접근법을 시도하세요."
        return "결과를 재검토하고 다른 전략을 시도하세요."

    # ─── Phase 3: REFLECT ─────────────────────────────────────

    def reflect(self, task: str, full_output: str) -> ReflectionResult:
        """작업 완료 후 성찰을 수행합니다."""
        result = ReflectionResult()

        # 이력 기반 자동 성찰
        for step in self._step_history:
            if step["passed"]:
                result.what_worked.append(
                    f"{step['tool']}: 성공 (등급 {step['grade']})"
                )
            else:
                result.what_failed.append(
                    f"{step['tool']}: 실패 — {', '.join(step['issues'])}"
                )

        # 실패율 계산
        total = len(self._step_history)
        if total > 0:
            fail_rate = len(result.what_failed) / total
            if fail_rate > 0.5:
                result.lessons.append(
                    f"이 작업의 실패율이 {fail_rate:.0%}로 높습니다. "
                    "접근 방식을 근본적으로 재검토해야 합니다."
                )
                result.should_retry = self._retry_count < self._max_retries
                result.retry_strategy = (
                    "이전에 실패한 도구/접근법을 피하고 완전히 다른 전략 사용"
                )
            elif fail_rate > 0.2:
                result.lessons.append(
                    f"일부 단계({len(result.what_failed)}건)에서 문제가 발생했습니다. "
                    "해당 패턴을 기억합니다."
                )

        return result

    def format_reflection_prompt(self, reflection: ReflectionResult) -> str:
        """성찰 결과를 에이전트 프롬프트에 주입할 텍스트로 포맷합니다."""
        if not reflection.what_failed and not reflection.lessons:
            return ""

        lines = ["\n<reflection>"]
        if reflection.what_worked:
            lines.append("✅ 성공한 것: " + "; ".join(reflection.what_worked[:3]))
        if reflection.what_failed:
            lines.append("❌ 실패한 것: " + "; ".join(reflection.what_failed[:3]))
        if reflection.lessons:
            lines.append("💡 교훈: " + "; ".join(reflection.lessons[:2]))
        if reflection.should_retry:
            lines.append("🔄 재시도 전략: " + reflection.retry_strategy)
        lines.append("</reflection>")

        return "\n".join(lines)

    # ─── Phase 4: ADAPT ──────────────────────────────────────

    def adapt_strategy(self, task: str, step_ctx) -> Optional[str]:
        """
        StepContext 상태를 분석하여 반복되는 오류가 있는지 확인하고,
        필요 시 에이전트의 전략을 동적으로 적응(Adapt)시킵니다.
        3회 이상 연속 실패 시 External Brain에 자동 위임합니다.
        """
        if not self._step_history:
            return None

        recent_failures = [s for s in self._step_history[-3:] if not s["passed"]]

        # 최근 3번 모두 실패 → External Brain 자동 위임
        if len(recent_failures) >= 3 and self._external_brain_router:
            delegation_result = self.auto_delegate_to_external_brain(
                task, recent_failures
            )
            if delegation_result:
                self._retry_count += 1
                return delegation_result

        # 최근 3번 중 2번 이상 실패한 경우 전략 변경 제안
        if len(recent_failures) >= 2:
            self._retry_count += 1
            tools_failed = list(set([f["tool"] for f in recent_failures]))

            adaptation = (
                "\n\n🚨 **[Cognitive Adapt] 전략 변경 필요** 🚨\n"
                f"최근 시도에서 계속 문제가 발생하고 있습니다 (실패 도구: {', '.join(tools_failed)}).\n"
                "기존 접근 방식을 완전히 버리고, 다음과 같이 적응하세요:\n"
                "1. 사용하던 도구를 바꾸거나, 인자를 근본적으로 다르게 설정하세요.\n"
                "2. 문제를 더 작은 단위로 쪼개어 단순한 도구부터 검증하세요.\n"
                "3. 파일 권한이나 환경의 제약이 있는지 확인하는 도구(예: run_bash_command로 ls -la)를 먼저 실행하세요.\n"
            )
            return adaptation

        return None

    def auto_delegate_to_external_brain(
        self, task: str, failures: List[Dict[str, Any]]
    ) -> Optional[str]:
        """
        반복 실패 시 External Brain(Gemini/ChatGPT)에 자동 위임하여
        전문가 조언을 받아 다음 시도에 주입합니다.

        Returns:
            외부 두뇌의 조언을 포함한 적응 프롬프트, 또는 None
        """
        if not self._external_brain_router:
            return None

        # 위임 프롬프트 구성: 실패 이력 + 원래 목표
        failure_summary = "\n".join(
            f"- 도구 '{f['tool']}': {', '.join(f.get('issues', []))}"
            for f in failures[:3]
        )

        delegation_prompt = (
            f"다음 작업을 수행하려 했으나 {len(failures)}회 연속 실패했습니다.\n\n"
            f"## 작업 목표\n{task}\n\n"
            f"## 실패 이력\n{failure_summary}\n\n"
            "위 실패 패턴을 분석하고, 이 문제를 해결하기 위한 "
            "구체적이고 실행 가능한 접근법을 3가지 제안해주세요. "
            "각 접근법에 사용할 도구/명령어와 예상 결과를 포함하세요."
        )

        try:
            import asyncio

            # 이벤트 루프가 있으면 그 안에서, 없으면 새로 생성
            try:
                _loop = asyncio.get_running_loop()  # noqa: F841
                # 이미 루프 안에 있으면 동기 폴백 사용
                logger.info(
                    "[CognitiveLoop] External Brain delegation "
                    "(async loop detected, scheduling)"
                )
                future = asyncio.ensure_future(
                    self._external_brain_router.send(
                        delegation_prompt, strategy="fallback"
                    )
                )
                # 타임아웃 30초
                result = asyncio.get_event_loop().run_until_complete(
                    asyncio.wait_for(future, timeout=30)
                )
            except RuntimeError:
                result = asyncio.run(
                    self._external_brain_router.send(
                        delegation_prompt, strategy="fallback"
                    )
                )

            if result and result.success and result.text:
                advice = result.text[:2000]
                logger.info(
                    f"[CognitiveLoop] External Brain advice received "
                    f"from {result.source} ({result.latency_ms:.0f}ms)"
                )

                # 실패 메모리에 저장
                if self.failure_memory:
                    self.failure_memory.record(
                        task=task,
                        error_pattern=f"3x_failure_{failures[0].get('tool', 'unknown')}",
                        fix_applied=f"external_brain_delegation_{result.source}",
                    )

                return (
                    "\n\n🧠 **[External Brain 자동 위임]** 🧠\n"
                    f"반복 실패를 감지하여 외부 AI({result.source})에 자동 위임했습니다.\n\n"
                    f"### 전문가 조언\n{advice}\n\n"
                    "위 조언을 참고하여 완전히 다른 접근법으로 재시도하세요."
                )

        except Exception as e:
            logger.warning(f"[CognitiveLoop] External Brain delegation failed: {e}")

        return None

    # ─── Phase 4: ADAPT ─────────────────────────────────────

    def adapt_for_retry(self) -> bool:
        """재시도 가능 여부를 판단하고, 가능하면 전략을 변경합니다."""
        if self._retry_count >= self._max_retries:
            return False

        self._retry_count += 1

        # 실패한 도구/접근법 목록을 다음 시도에서 제외
        failed_tools = [s["tool"] for s in self._step_history if not s["passed"]]

        logger.info(
            f"[CognitiveLoop] Adapting for retry {self._retry_count}/{self._max_retries}. "
            f"Excluding failed tools: {failed_tools}"
        )
        return True

    def get_anti_patterns(self) -> List[str]:
        """이번 세션에서 실패한 패턴 목록을 반환합니다 (프롬프트 주입용)."""
        patterns = []
        for step in self._step_history:
            if not step["passed"]:
                patterns.append(
                    f"'{step['tool']}' 사용 시 다음 문제 발생: {', '.join(step['issues'])}"
                )
        return patterns

    def reset(self):
        """새 작업을 위해 루프를 초기화합니다."""
        self._current_plan = None
        self._step_history = []
        self._retry_count = 0


# ─── Plan-Execute 분리 엔진 (Graph-of-Thought 지원) ───────────────


class PlannerExecutor:
    """
    고수준 Planner-Executor 분리 엔진.

    기존 CognitiveLoop가 도구 실행 검증에 집중한다면,
    PlannerExecutor는 **작업 전체의 계획 수립과 병렬 실행**을 담당합니다.

    아키텍처:
        1. Plan Phase: 작업을 DAG(방향 비순환 그래프)로 분해
        2. Execute Phase: 병렬 가능한 스텝을 asyncio.gather로 동시 실행
        3. Validate Phase: 결과 검증 + 필요시 re-plan
        4. Consolidate Phase: 결과 통합 및 최종 출력

    사용법:
        planner = PlannerExecutor(cognitive_loop)
        result = await planner.run(task, executor_fn)
    """

    def __init__(
        self, cognitive_loop: Optional[CognitiveLoop] = None, max_replans: int = 2
    ):
        self.cognitive_loop = cognitive_loop or CognitiveLoop()
        self.max_replans = max_replans
        self._replan_count = 0
        self._execution_trace: List[Dict[str, Any]] = []

    def decompose_task(
        self, task: str, available_tools: List[str] = None
    ) -> ExecutionPlan:
        """
        작업을 실행 계획으로 분해합니다 (동기, LLM 호출 없이 휴리스틱).

        복잡한 작업을 식별하여 병렬 실행 가능한 그룹으로 나눕니다.
        """
        plan = ExecutionPlan(
            goal=task,
            created_at=datetime.now().isoformat(),
            reasoning="Task decomposition via PlannerExecutor",
        )

        # 기본: 단일 스텝 (외부에서 LLM을 통해 더 정교한 계획 생성 가능)
        plan.steps.append(
            PlanStep(
                step_id=1,
                description=task,
                status="pending",
            )
        )

        return plan

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        executor_fn,  # async callable(step: PlanStep) -> str
    ) -> Dict[str, Any]:
        """
        실행 계획을 수행합니다. 병렬 가능한 스텝은 동시 실행합니다.

        Args:
            plan: 실행 계획
            executor_fn: 각 스텝을 실행하는 비동기 함수

        Returns:
            {"success": bool, "results": [...], "trace": [...]}
        """
        import asyncio

        results = []

        # 병렬 그룹별로 실행
        parallel_groups = self._group_parallel_steps(plan.steps)

        for group_idx, group in enumerate(parallel_groups):
            if len(group) > 1:
                # 병렬 실행
                logger.info(
                    f"[PlannerExecutor] 병렬 실행 그룹 {group_idx+1}: {len(group)}개 스텝"
                )
                group_results = await asyncio.gather(
                    *[self._execute_step(step, executor_fn) for step in group],
                    return_exceptions=True,
                )
                for step, result in zip(group, group_results):
                    if isinstance(result, Exception):
                        step.status = "failed"
                        step.result = str(result)
                    results.append(
                        {
                            "step": step.step_id,
                            "result": step.result,
                            "status": step.status,
                        }
                    )
            else:
                # 순차 실행
                step = group[0]
                await self._execute_step(step, executor_fn)
                results.append(
                    {"step": step.step_id, "result": step.result, "status": step.status}
                )

        # 검증
        all_passed = all(s.status == "done" for s in plan.steps)

        # 실패 시 re-plan 시도
        if not all_passed and self._replan_count < self.max_replans:
            self._replan_count += 1
            failed_steps = [s for s in plan.steps if s.status == "failed"]
            logger.info(
                f"[PlannerExecutor] Re-plan #{self._replan_count}: "
                f"{len(failed_steps)}개 스텝 실패"
            )
            # 실패한 스텝만 재시도
            for step in failed_steps:
                step.status = "pending"
                step.result = None
                await self._execute_step(step, executor_fn)
                results.append(
                    {
                        "step": step.step_id,
                        "result": step.result,
                        "status": step.status,
                        "retry": True,
                    }
                )

        trace_entry = {
            "plan_goal": plan.goal,
            "total_steps": len(plan.steps),
            "replans": self._replan_count,
            "success": all(s.status == "done" for s in plan.steps),
            "timestamp": datetime.now().isoformat(),
        }
        self._execution_trace.append(trace_entry)

        return {
            "success": trace_entry["success"],
            "results": results,
            "trace": trace_entry,
        }

    async def _execute_step(self, step: PlanStep, executor_fn) -> str:
        """단일 스텝을 실행하고 CognitiveLoop의 검증을 적용합니다."""
        step.status = "running"
        try:
            result = await executor_fn(step)
            step.result = result if isinstance(result, str) else str(result)

            # CognitiveLoop의 도구 결과 검증 적용
            if step.tool and self.cognitive_loop:
                verification = self.cognitive_loop.verify_tool_result(
                    step.tool, step.args or {}, step.result
                )
                step.verification = json.dumps(verification, ensure_ascii=False)
                if verification["passed"]:
                    step.status = "done"
                else:
                    step.status = "failed"
            else:
                step.status = "done"

            return step.result
        except Exception as e:
            step.status = "failed"
            step.result = f"Error: {e}"
            logger.error(f"[PlannerExecutor] Step {step.step_id} failed: {e}")
            return step.result

    def _group_parallel_steps(self, steps: List[PlanStep]) -> List[List[PlanStep]]:
        """
        스텝들을 병렬 실행 가능한 그룹으로 분류합니다.

        현재: 의존성 없는 연속 스텝을 같은 그룹으로 묶음.
        향후: DAG 기반 의존성 분석으로 확장 가능.
        """
        if not steps:
            return []

        # 기본 구현: 각 스텝을 개별 그룹으로 (순차 실행)
        # TODO: step.depends_on 필드 추가 후 DAG 기반 병렬 그루핑
        return [[step] for step in steps]

    def get_execution_trace(self) -> List[Dict[str, Any]]:
        """실행 궤적을 반환합니다 (관찰성/디버깅용)."""
        return self._execution_trace

    def reset(self):
        """상태를 초기화합니다."""
        self._replan_count = 0
        self._execution_trace = []
        self.cognitive_loop.reset()
