"""Workflow/mode slash command handlers (mixin).

Provides: /qa, /goal, /mode, /plan, /build, /aishell, /benchmark,
/dialectic, /finance, and the shared /_cmd_lifecycle handler.

These handlers access ``self._model_manager``, ``self._tool_registry``,
``self._session_manager``, ``self._mode_manager``, and ``self._skill_loader``.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class SlashCommandWorkflowMixin:
    """Workflow, mode, and heavy-computation command handlers.

    Note: The following attributes are provided by ``SlashCommandRegistryBase``
    via cooperative multiple inheritance (MRO).
    """

    # Mixin-required attributes (resolved via MRO at runtime)
    _tool_registry: Any
    _model_manager: Any
    _session_manager: Any
    _mode_manager: Any
    _skill_loader: Any
    _execute_natural_language: Any

    def _cmd_qa(self, args: list) -> str:
        """대시보드 DOM 기반 자가 점검."""
        if not self._tool_registry or "fetch_dom" not in self._tool_registry._tools:
            return "❌ `fetch_dom` 도구가 레지스트리에 없습니다."

        url = args[0] if args else "http://127.0.0.1:8000/"
        tool = self._tool_registry._tools["fetch_dom"]

        goto_res = tool.execute(action="goto", url=url)
        if "Error" in goto_res:
            return f"❌ QA 실패: 접속 중 오류 발생\n\n```text\n{goto_res}\n```"

        result = tool.execute(action="extract", selector="#app")
        tool.execute(action="close")

        if "Error" in result or "error" in result.lower() and "browser" in result.lower():
            return f"❌ QA 실패: DOM 추출 중 오류 발생\n\n```text\n{result}\n```"

        report = [f"🔍 **QA 점검 보고서 ({url})**\n"]

        if len(result) < 50:
            report.append("⚠️ **화면 빈 렌더링 의심:** DOM 텍스트가 너무 짧습니다.")
        else:
            report.append("✅ **화면 렌더링 정상:** DOM 요소 감지됨.")

        error_keywords = ["연결 실패", "에러", "500 Internal", "Cannot fetch"]
        found_errors = [kw for kw in error_keywords if kw in result]
        if found_errors:
            report.append(f"❌ **UI 에러 발생:** 화면 내 에러 키워드: {', '.join(found_errors)}")
        else:
            report.append("✅ **UI 에러 없음:** 화면 내 치명적 에러 문구 미감지.")

        model_keywords = ["qwen", "deepseek", "llama", "phi"]
        found_models = [kw for kw in model_keywords if kw.lower() in result.lower()]
        if found_models:
            report.append(f"✅ **모델 로드 확인:** {', '.join(found_models)}")
        else:
            report.append("⚠️ **모델 미발견:** 설치된 로컬 모델 목록을 찾을 수 없습니다.")

        report.append("\n**추출된 DOM 텍스트 요약 (최대 300자):**")
        report.append(f"```text\n{result[:300]}...\n```")
        return "\n".join(report)

    def _cmd_goal(self, args: list) -> str:
        """자율 목표 계약 생성."""
        objective = " ".join(args).strip()
        if not objective:
            objective = ""

        context = {}
        if self._session_manager:
            try:
                context["session"] = self._session_manager.get_session_info()
            except Exception:
                logger.exception("Unhandled exception")
                context["session"] = "unavailable"
        if self._tool_registry:
            try:
                context["tool_count"] = len(self._tool_registry)
            except Exception:
                logger.exception("Unhandled exception")
                context["tool_count"] = "unknown"

        from antigravity_k.engine.goal_runner import GoalRunner

        runner = GoalRunner()
        report = runner.run(objective, context=context)
        return runner.render_markdown(report)

    def _cmd_mode(self, args: list) -> str:
        """/mode 명령어: 실행 모드 상태 표시 및 변경."""
        if not args:
            return self._mode_status()

        sub = args[0].lower()
        if sub in ("status", "info"):
            return self._mode_status()
        if sub == "plan":
            return self._mode_switch_plan(args[1:])
        if sub == "build":
            return self._mode_switch_build(args[1:])
        if sub == "interactive":
            return self._mode_switch_interactive()
        return "Usage: /mode [plan|build|interactive|status]"

    def _cmd_plan(self, args: list) -> str:
        """/plan 명령어: Plan 모드로 전환."""
        reason = " ".join(args).strip() if args else "사용자 요청 (/plan)"
        return self._mode_switch_plan(args if args else [reason])

    def _cmd_build(self, args: list) -> str:
        """/build 명령어: Build 모드로 전환."""
        return self._mode_switch_build(args)

    def _mode_status(self) -> str:
        """현재 모드 상태를 반환합니다."""
        if not hasattr(self, "_mode_manager") or self._mode_manager is None:
            return "ModeManager not connected. Use the main session to access mode control."
        return self._mode_manager.format_status()

    def _mode_switch_plan(self, args: list) -> str:
        """Plan 모드로 전환합니다."""
        if not hasattr(self, "_mode_manager") or self._mode_manager is None:
            return "ModeManager not connected."

        reason = " ".join(args).strip() if args else "사용자 요청 (/plan)"
        if self._mode_manager.switch_to_plan(reason):
            return f"✅ **PLAN 모드로 전환되었습니다.**\n\n{self._mode_manager.format_status()}"
        return "❌ PLAN 모드 전환에 실패했습니다."

    def _mode_switch_build(self, args: list) -> str:
        """Build 모드로 전환합니다."""
        if not hasattr(self, "_mode_manager") or self._mode_manager is None:
            return "ModeManager not connected."

        plan_path = args[0] if args else None
        reason = "사용자 요청 (/build)"

        if plan_path:
            self._mode_manager.set_plan_artifact(plan_path)
            self._mode_manager.set_plan_quality_passed(True)
            reason = f"Plan 아티팩트 '{plan_path}' 기반 Build 모드 전환"

        if self._mode_manager.switch_to_build(plan_artifact_path=plan_path, reason=reason):
            return f"✅ **BUILD 모드로 전환되었습니다.**\n\n{self._mode_manager.format_status()}"

        if self._mode_manager.is_plan:
            return (
                "❌ BUILD 모드 전환에 실패했습니다.\n\n"
                "Plan → Build 자동 전환 조건이 충족되지 않았습니다:\n"
                "1. Plan 아티팩트(`implementation_plan.md`)가 생성되었는지 확인하세요.\n"
                "2. Plan 품질 검증(QualityGate)이 통과되어야 합니다.\n"
                "3. 강제 전환: `/build <plan_artifact_path>` 로 경로를 직접 지정할 수 있습니다."
            )
        return "❌ BUILD 모드 전환에 실패했습니다."

    def _mode_switch_interactive(self) -> str:
        """Interactive 모드로 전환합니다."""
        if not hasattr(self, "_mode_manager") or self._mode_manager is None:
            return "ModeManager not connected."
        if self._mode_manager.switch_to_interactive("사용자 요청 (/mode interactive)"):
            return f"✅ **INTERACTIVE 모드로 전환되었습니다.**\n\n{self._mode_manager.format_status()}"
        return "❌ INTERACTIVE 모드 전환에 실패했습니다."

    def _cmd_aishell(self, args: list) -> str:
        """자연어 의도를 받아 Bash 코드로 변환 후 실행합니다."""
        if not args:
            return "Usage: `/aishell <자연어 명령어>`"

        intent = " ".join(args)
        if not self._model_manager:
            return "❌ Error: Model manager is not connected."

        prompt = (
            f"Translate the following task to a macOS shell command. "
            f"Provide ONLY the command in ONE LINE, with no explanation:\n\n"
            f"Task: {intent}"
        )

        info = self._model_manager.get_model_info()
        target_model = (
            info.get("active_model", "default") if isinstance(info, dict) else getattr(info, "active_model", "default")
        )
        if target_model == "default" or not target_model:
            target_model = "local-model"

        try:
            from antigravity_k.engine.orchestrator import OrchestratorAgent

            orchestrator = OrchestratorAgent(model_manager=self._model_manager)
            messages = [{"role": "user", "content": prompt}]
            command = orchestrator.run_sync(messages, target_model=target_model).strip()

            if command.startswith("```"):
                lines = command.split("\n")
                command = (
                    "\n".join(lines[1:-1])
                    if len(lines) > 2
                    else command.replace("```bash", "").replace("```sh", "").replace("```", "")
                )
        except Exception as e:
            logger.exception("Unhandled exception")
            return f"❌ 명령어 번역 실패: {e}"

        if not self._tool_registry or "run_bash_command" not in self._tool_registry._tools:
            return f"번역된 명령어: `{command}`\n\n(실행 실패: run_bash_command 도구를 찾을 수 없습니다.)"

        tool = self._tool_registry._tools["run_bash_command"]
        output = tool.execute(command=command, background=False)

        return (
            f"🤖 **AiShell 변환 완료**\n"
            f"> 원본: `{intent}`\n"
            f"> 명령: `{command}`\n\n"
            f"**실행 결과:**\n```text\n{output}\n```"
        )

    def _cmd_benchmark(self, args: list) -> str:
        """벤치마크 실행/보고서 출력."""
        if not self._model_manager:
            return "❌ ModelManager가 필요합니다."

        from antigravity_k.engine.benchmark_harness import BenchmarkHarness

        harness = BenchmarkHarness(model_manager=self._model_manager)

        if not args:
            return (
                "📊 **Benchmark 명령어**\n\n"
                "- `/benchmark run` — 전체 스위트 실행\n"
                "- `/benchmark run sim-001` — 특정 과제만 실행\n"
                "- `/benchmark run simple` — 카테고리별 실행\n"
                "- `/benchmark report` — 누적 비교표 출력\n"
                "- `/benchmark clear` — 누적 결과 초기화"
            )

        sub = args[0].lower()

        if sub == "run":
            suite_name = args[1] if len(args) > 1 else "all"

            def _run_stream():
                yield "🚀 **벤치마크 실행 시작**\n\n"
                yield f"스위트: `{suite_name}`\n\n"
                yield "⏳ 과제를 순차 실행 중입니다. VRAM 경합 방지를 위해 하나씩 처리합니다...\n\n"
                try:
                    report = harness.run_suite(suite_name)
                    yield f"✅ **벤치마크 완료** ({report.duration_s:.1f}s, {len(report.results)}건)\n\n"
                    yield harness.comparison_table(suite_name)
                except Exception as e:
                    logger.exception("Unhandled exception")
                    yield f"❌ 벤치마크 실행 실패: {e}"

            return _run_stream()

        elif sub == "report":
            suite_name = args[1] if len(args) > 1 else "all"
            return harness.comparison_table(suite_name)

        elif sub == "clear":
            harness.clear_history()
            return "🗑️ 벤치마크 누적 결과가 초기화되었습니다."

        return f"❓ 알 수 없는 하위 명령: `{sub}`. `/benchmark` 로 도움말을 확인하세요."

    def _cmd_dialectic(self, args: list) -> str:
        """변증법적 추론 실행 — Hegelion 패턴."""
        query = " ".join(args).strip()
        if not query:
            return (
                "⚖️ **변증법적 추론 엔진 (Hegelion)**\n\n"
                "Usage: `/dialectic <질문 또는 문제>`\n\n"
                "3단계 추론 (Thesis→Antithesis→Synthesis)으로\n"
                "문제를 다각도로 심층 분석합니다.\n\n"
                "Council 모드: `/dialectic council: <질문>` — "
                "Logician·Empiricist·Ethicist 3인 위원회 비판\n"
            )

        from antigravity_k.engine.dialectic_engine import DialecticEngine

        engine = DialecticEngine()
        use_council = query.lower().startswith("council:")
        if use_council:
            query = query[len("council:") :].strip()

        prompt = engine.create_single_shot_prompt(query, use_council=use_council)

        if self._model_manager:
            try:
                from antigravity_k.engine.orchestrator import OrchestratorAgent

                orchestrator = OrchestratorAgent(model_manager=self._model_manager)
                messages = [{"role": "user", "content": prompt}]
                info = self._model_manager.get_model_info()
                target = (
                    info.get("active_model", "default")
                    if isinstance(info, dict)
                    else getattr(info, "active_model", "default")
                )
                raw_result = orchestrator.run_sync(messages, target_model=target)
                result = engine.parse_structured_response(raw_result, query)
                return engine.render_markdown(result)
            except Exception as e:
                logger.error("Dialectic execution error: %s", e, exc_info=True)
                return f"⚠️ 변증법 추론 실행 오류: {e}\n\n아래 프롬프트를 직접 사용할 수 있습니다:\n\n```\n{prompt[:500]}...\n```"  # noqa: E501

        return (
            "⚖️ **변증법적 추론 프롬프트 생성 완료**\n\n"
            "로컬 모델이 연결되지 않아 프롬프트만 생성합니다.\n"
            "아래 프롬프트를 LLM에 직접 전달하세요:\n\n"
            f"```\n{prompt}\n```"
        )

    def _cmd_finance(self, args: list) -> str:
        """금융 어시스턴트 커맨드 라우터 (/finance, /comps, /dcf)."""
        query = " ".join(args).strip()
        return (
            "💼 **Financial Assistant 가동 준비 완료**\n\n"
            f"요청하신 분석 대상: `{query if query else '미지정'}`\n\n"
            "Antigravity-K 시스템이 **financial-assistant** 및 **fa-modeling** 스킬을 장착했습니다.\n"
            "이제 DCF(가치평가), Comps(비교분석), 3-Statement 모델링 등 전문 금융 분석 요청을 자유롭게 대화로 이어가세요!\n"
            '(예시: "해당 기업의 과거 3년 재무 데이터를 기반으로 DCF 모델을 작성해줘. Base/Bear/Bull 시나리오를 적용해.")'
        )

    def _cmd_lifecycle(self, command_name: str, args: list) -> str:
        """Lifecycle command handler (e.g. /spec, /build)."""
        prompt = " ".join(args).strip()

        skill_maps = {
            "spec": "spec-driven-development",
            "plan": "planning-and-task-breakdown",
            "build": "incremental-implementation",
            "test": "test-driven-development",
            "review": "code-review-and-quality",
            "code-simplify": "code-simplification",
            "ship": "shipping-and-launch",
        }

        skill_name = skill_maps.get(command_name, command_name)

        if self._skill_loader:
            try:
                self._skill_loader.activate(skill_name)
            except Exception:
                logger.exception("Could not explicitly activate skill %s", skill_name)

        system_injection = (
            f"ACTIVATE LIFECYCLE SKILL: {skill_name}.\n"
            f"Please strictly follow the workflow and verification gates defined for this skill.\n"
            f"Task: {prompt}"
        )
        return self._execute_natural_language(system_injection)
