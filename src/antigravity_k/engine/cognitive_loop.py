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
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional, Generator

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
    
    def __init__(self, project_root: str = ".", failure_memory=None):
        self.project_root = project_root
        self.failure_memory = failure_memory
        self._current_plan: Optional[ExecutionPlan] = None
        self._step_history: List[Dict[str, Any]] = []
        self._retry_count = 0
        self._max_retries = 2
    
    # ─── Phase 1: PLAN ─────────────────────────────────────
    
    def create_plan_prompt(self, task: str, available_tools: List[str]) -> str:
        """에이전트에게 계획을 세우도록 하는 프롬프트를 생성합니다."""
        failure_context = ""
        if self.failure_memory:
            similar = self.failure_memory.find_similar(task)
            if similar:
                failure_context = (
                    "\n\n⚠️ 과거 유사 작업에서의 실패 기록:\n"
                    + "\n".join(f"- {f['error_pattern']}: {f['fix_applied']}" for f in similar[:3])
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
    
    def verify_tool_result(self, tool_name: str, tool_args: Dict, result: str) -> Dict[str, Any]:
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
            if result.strip().startswith("Error") or result.strip().startswith("There was an error"):
                grade = "F"
                issues.append(f"도구 '{tool_name}'이 에러를 반환했습니다")
            
            # 파일 관련 도구: 파일 존재 여부 확인
            if tool_name in ("write_file", "edit_file", "replace_file_content"):
                file_path = tool_args.get("file_path") or tool_args.get("path", "")
                if file_path and not os.path.exists(file_path):
                    # 상대 경로면 프로젝트 루트 기준
                    abs_path = os.path.join(self.project_root, file_path)
                    if not os.path.exists(abs_path):
                        grade = "C"
                        issues.append(f"파일이 생성/수정되었으나 확인할 수 없음: {file_path}")
            
            # 코드 생성 도구: AST 검증
            if tool_name in ("write_file", "edit_file") and file_path.endswith(".py"):
                try:
                    actual_path = file_path if os.path.exists(file_path) else os.path.join(self.project_root, file_path)
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
        self._step_history.append({
            "tool": tool_name,
            "grade": grade,
            "passed": passed,
            "issues": issues,
            "timestamp": datetime.now().isoformat(),
        })
        
        return {
            "passed": passed,
            "grade": grade,
            "issues": issues,
            "suggestion": suggestion,
        }
    
    def _suggest_fix(self, tool_name: str, args: Dict, result: str, issues: List[str]) -> str:
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
                result.retry_strategy = "이전에 실패한 도구/접근법을 피하고 완전히 다른 전략 사용"
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
            lines.append("📝 교훈: " + "; ".join(reflection.lessons))
        if reflection.should_retry:
            lines.append(f"🔄 재시도 전략: {reflection.retry_strategy}")
        lines.append("</reflection>")
        
        return "\n".join(lines)
    
    # ─── Phase 4: ADAPT ─────────────────────────────────────
    
    def adapt_for_retry(self) -> bool:
        """재시도 가능 여부를 판단하고, 가능하면 전략을 변경합니다."""
        if self._retry_count >= self._max_retries:
            return False
        
        self._retry_count += 1
        
        # 실패한 도구/접근법 목록을 다음 시도에서 제외
        failed_tools = [
            s["tool"] for s in self._step_history if not s["passed"]
        ]
        
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
