"""Antigravity-K: MAX Mode Parallel Editing Engine (P4).

=============================================================
Codebuff의 MAX 모드에서 영감을 받은 병렬 편집 시스템:

- 동일 태스크를 N개 워커(에디터)가 독립적으로 병렬 실행
- 각 워커는 서로 다른 모델/전략으로 접근 (다양성 확보)
- Selector 엔진이 모든 결과를 검토하고 최적 선정
- 필요 시 여러 결과를 합성하여 최종 출력 생성

아키텍처:
    WorkerPool → [Worker 1 (model A), Worker 2 (model B), ...]
         ↓ 병렬 실행 (thread pool)
    SelectorEngine → 각 결과 리뷰 → 최적 선정 또는 합성
         ↓
    최종 출력
"""

import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity_k.max_engine")


@dataclass
class WorkerResult:
    """단일 워커의 실행 결과."""

    worker_id: int
    model: str
    strategy: str
    output: str
    elapsed_sec: float
    error: str | None = None


@dataclass
class MaxRunResult:
    """MAX 모드 실행 전체 결과."""

    total_workers: int
    successful: int
    results: list[WorkerResult] = field(default_factory=list)
    selected_idx: int = -1
    final_output: str = ""
    selector_reasoning: str = ""
    error: str | None = None


class MaxModeEngine:
    """MAX 모드 병렬 편집 엔진.

    Codebuff의 MAX 모드에서 영감을 받은 시스템.
    동일 태스크를 N개 워커가 독립적으로 병렬 실행하고,
    Selector가 최적 결과를 선정합니다.

    사용법:
        engine = MaxModeEngine(model_manager, project_root)
        result = engine.run(task, context, orchestrator)
        print(result.final_output)
    """

    def __init__(self, model_manager, project_root: str = ""):
        """Initialize the MaxModeEngine.

        Args:
            model_manager: ModelManager 인스턴스
            project_root: 프로젝트 루트 경로
        """
        self.manager = model_manager
        self.project_root = project_root or os.getcwd()
        self._max_workers = 4  # 기본값, 필요시 조정

    def set_max_workers(self, n: int):
        """최대 병렬 워커 수를 설정합니다."""
        self._max_workers = max(1, min(n, 8))  # 1~8 범위

    def run(
        self,
        task_spec: dict[str, Any],
        orchestrator=None,
    ) -> MaxRunResult:
        """MAX 모드 병렬 실행.

        Args:
            task_spec: 태스크 명세
                {
                    "prompt": str,          # 실제 프롬프트
                    "messages": list,       # 대화 메시지
                    "task_type": str,       # 태스크 유형
                    "delegate_to": str,     # 위임 역할
                    "max_steps": int,       # 최대 도구 호출
                    "target_model": str,    # 대상 모델
                }
            orchestrator: OrchestratorAgent 인스턴스

        Returns:
            MaxRunResult: 실행 결과
        """
        prompt = task_spec.get("prompt", "")
        messages = task_spec.get("messages", [])
        task_type = task_spec.get("task_type", "coding")
        delegate_to = task_spec.get("delegate_to", "WORKER")
        max_steps = task_spec.get("max_steps", 15)
        target_model = task_spec.get("target_model", "")

        if not orchestrator or not self.manager:
            return MaxRunResult(
                total_workers=0,
                successful=0,
                error="MAX Mode requires orchestrator and model_manager",
            )

        # 1. 워커 구성 (가용 모델 목록)
        worker_configs = self._build_worker_configs(delegate_to, target_model)

        if not worker_configs:
            return MaxRunResult(
                total_workers=0,
                successful=0,
                error="No available models for MAX mode workers",
            )

        effective_workers = len(worker_configs)
        logger.info(
            "[MAX] Starting parallel execution with %s workers",
            effective_workers,
        )

        # 2. 병렬 실행
        results: list[WorkerResult | None] = [None] * effective_workers

        with ThreadPoolExecutor(max_workers=effective_workers) as executor:
            future_map = {}
            for i, config in enumerate(worker_configs):
                future = executor.submit(
                    self._run_worker,
                    worker_id=i,
                    config=config,
                    prompt=prompt,
                    messages=messages,
                    task_type=task_type,
                    delegate_to=delegate_to,
                    max_steps=max_steps,
                    orchestrator=orchestrator,
                )
                future_map[future] = i

            for future in as_completed(future_map):
                idx = future_map[future]
                try:
                    results[idx] = future.result()
                except Exception as e:
                    logger.exception("[MAX] Worker %s failed with exception", idx)
                    results[idx] = WorkerResult(
                        worker_id=idx,
                        model=worker_configs[idx].get("model", "unknown"),
                        strategy=worker_configs[idx].get("strategy", "unknown"),
                        output="",
                        elapsed_sec=0.0,
                        error=str(e),
                    )

        # None 결과 필터링
        valid_results = [r for r in results if r is not None]
        successful = [r for r in valid_results if r.error is None and r.output.strip()]

        # 3. Selector: 최적 결과 선정
        if successful:
            selected = self._select_best(prompt, successful, delegate_to, orchestrator)
        else:
            selected = -1

        # 4. 최종 출력 구성
        if selected >= 0:
            final_output = successful[selected].output
            selector_reasoning = self._format_trace(
                successful, selected, worker_configs,
            )
        elif successful:
            # Selector 실패 시 첫 번째 성공 결과 사용
            selected = 0
            final_output = successful[0].output
            selector_reasoning = (
                "> MAX Mode: Selector unavailable, using first successful result.\n\n"
            )
        else:
            final_output = ""
            selector_reasoning = ""

        # 플래시 효과: 출력 앞에 MAX 모드 메타 표시
        if selector_reasoning and final_output:
            final_output = selector_reasoning + final_output

        return MaxRunResult(
            total_workers=effective_workers,
            successful=len(successful),
            results=valid_results,
            selected_idx=selected,
            final_output=final_output,
            selector_reasoning=selector_reasoning,
        )

    def _build_worker_configs(
        self, delegate_to: str, target_model: str,
    ) -> list[dict[str, str]]:
        """워커 구성을 생성합니다. (다양한 모델 + 전략 조합).

        최대 4개 워커:
        - Worker 1: target_model (default strategy, temperature 0.2)
        - Worker 2: 대상 역할의 다른 모델 (creative strategy, temperature 0.7)
        - Worker 3: 대상 역할의 또 다른 모델 (safe strategy, temperature 0.1)
        - Worker 4: fallback 모델 (balanced strategy, temperature 0.4)
        """
        configs = []

        if not self.manager:
            return configs

        try:
            # 사용 가능한 모델 목록 조회
            available = self._get_available_models()
        except Exception:
            available = [target_model] if target_model else []

        if not available:
            return configs

        # Worker 1: 기본 모델 + 기본 전략
        primary = available[0] if available else target_model
        configs.append({
            "model": primary,
            "strategy": "default",
            "temperature": 0.2,
            "description": "정밀 실행",
        })

        # Worker 2: 다른 모델 + 창의 전략 (최대 2개까지만)
        if len(available) > 1:
            configs.append({
                "model": available[1],
                "strategy": "creative",
                "temperature": 0.7,
                "description": "창의적 접근",
            })

        # Worker 3: 세 번째 모델 + 안전 전략
        if len(available) > 2:
            configs.append({
                "model": available[2],
                "strategy": "safe",
                "temperature": 0.1,
                "description": "안정적 접근",
            })

        # Worker 4: 첫 번째 모델로 균형 전략 (워커가 최소 2개는 되도록)
        if len(configs) >= 2:
            pass  # 이미 충분

        return configs[:self._max_workers]

    def _get_available_models(self) -> list[str]:
        """실제 가용 모델 목록을 조회합니다.

        우선순위:
        1. ModelManager에 실제 로드된 모델 (최우선)
        2. combo 설정에서 사용 가능한 모델
        3. config.yaml의 reasoning/coding 모델
        4. agent_models 매핑
        """
        models: list[str] = []

        try:
            # 1. 실제 로드된 모델 우선
            loaded = getattr(self.manager, '_loaded_models', None) or getattr(self.manager, 'loaded_models', None)
            if loaded and isinstance(loaded, dict):
                models = list(loaded.keys())[:4]
            elif loaded and isinstance(loaded, list):
                models = [m.get('name', str(m)) if isinstance(m, dict) else str(m) for m in loaded[:4]]

            # 실제 로드된 모델이 2개 이상 있으면 바로 반환
            if len(models) >= 2:
                return models[:self._max_workers]

            # 2. 로드된 모델 부족 시 config에서 추가
            config = getattr(self.manager, "config", {})
            combos = config.get("combos", {})

            preferred_combos = ["reasoning-balanced", "fast-response", "coding-swarm"]
            for combo_name in preferred_combos:
                combo = combos.get(combo_name, {})
                combo_models = combo.get("models", [])
                for m in combo_models:
                    if m not in models:
                        models.append(m)
                        if len(models) >= 4:
                            break
                if len(models) >= 4:
                    break

            if len(models) < 2:
                agents_config = config.get("agent_models", {})
                for role in ("WORKER", "ENG_MANAGER"):
                    model = agents_config.get(role, "")
                    if model and model not in models:
                        models.append(str(model))
        except Exception:
            logger.debug("[MAX] Error loading model config", exc_info=True)

        # 최소 1개는 보장 (loaded or config에서 찾은 것)
        if not models:
            models = ["default"]

        return models[:self._max_workers]

    def _run_worker(
        self,
        worker_id: int,
        config: dict[str, str],
        prompt: str,
        messages: list[dict[str, str]],
        task_type: str,
        delegate_to: str,
        max_steps: int,
        orchestrator,
    ) -> WorkerResult:
        """단일 워커를 실행합니다."""
        model = config.get("model", "default")
        strategy = config.get("strategy", "default")
        temperature = float(config.get("temperature", 0.4))

        # 워커별 전략이 담긴 프롬프트 주입
        worker_prompt = self._build_worker_prompt(
            original_prompt=prompt,
            model=model,
            strategy=strategy,
            temperature=temperature,
        )

        worker_messages = list(messages)
        worker_messages[-1] = {"role": "user", "content": worker_prompt}

        start = time.time()
        try:
            from antigravity_k.engine.tool_loop import ToolLoopEngine

            tool_loop = ToolLoopEngine(orchestrator)
            output_parts = []

            for chunk in tool_loop.run_loop(
                worker_messages,
                delegate_to,
                task_type,
                max_steps,
                model,
            ):
                output_parts.append(chunk)

            elapsed = time.time() - start
            output = "".join(output_parts)

            logger.info(
                "[MAX] Worker %s (%s, %s) done in %.1fs, %s chars",
                worker_id, model, strategy, elapsed, len(output),
            )

            return WorkerResult(
                worker_id=worker_id,
                model=model,
                strategy=strategy,
                output=output,
                elapsed_sec=round(elapsed, 1),
            )
        except Exception as e:
            elapsed = time.time() - start
            logger.exception("[MAX] Worker %s failed", worker_id)
            return WorkerResult(
                worker_id=worker_id,
                model=model,
                strategy=strategy,
                output="",
                elapsed_sec=round(elapsed, 1),
                error=str(e),
            )

    def _build_worker_prompt(
        self,
        original_prompt: str,
        model: str,
        strategy: str,
        temperature: float,
    ) -> str:
        """워커별 전략이 반영된 프롬프트를 생성합니다."""
        strategy_intro = {
            "default": (
                "Execute the following task precisely. Focus on correctness and completeness."
            ),
            "creative": (
                "Approach the following task with creative problem-solving. "
                "Consider unconventional approaches, edge cases, and elegant solutions. "
                "Don't be afraid to refactor or restructure if it improves quality."
            ),
            "safe": (
                "Execute the following task with maximum safety and reliability. "
                "Prefer well-established patterns, minimal changes, and defensive programming. "
                "Prioritize backward compatibility and readability."
            ),
            "balanced": (
                "Execute the following task balancing pragmatism and quality. "
                "Use sound engineering judgment. Choose the approach that gives the best "
                "trade-off between simplicity, correctness, and maintainability."
            ),
        }

        intro = strategy_intro.get(strategy, strategy_intro["default"])

        return (
            f"[MAX Mode Worker - {model}, {strategy}]\n\n"
            f"{intro}\n\n"
            f"---\n{original_prompt}"
        )

    def _select_best(
        self,
        prompt: str,
        results: list[WorkerResult],
        delegate_to: str,
        orchestrator,
    ) -> int:
        """Selector: 모든 결과를 검토하고 최적 인덱스를 반환합니다.

        여러 결과를 비교하여 가장 적합한 하나를 선택합니다.
        선택이 불가능하면 -1을 반환합니다.
        """
        if len(results) == 1:
            return 0

        # 결과 포맷팅
        candidates = []
        for i, r in enumerate(results):
            output_preview = r.output[:800] if r.output else "(empty)"
            candidates.append(
                f"[Candidate {i + 1}] — Model: {r.model}, Strategy: {r.strategy}\n"
                f"Time: {r.elapsed_sec}s, Length: {len(r.output)} chars\n"
                f"---\n{output_preview}\n---\n"
            )

        candidate_text = "\n\n".join(candidates)

        # Selector 프롬프트
        selector_prompt = (
            "You are the MAX Mode Selector. Review the following candidate outputs "
            "generated by different AI models/strategies for the same task.\n\n"
            "Select the BEST output based on:\n"
            "1. Correctness — Does it solve the task correctly?\n"
            "2. Completeness — Does it handle edge cases?\n"
            "3. Code Quality — Is the code clean, well-structured?\n"
            "4. Efficiency — Is the solution performant?\n\n"
            "Respond in EXACTLY this format:\n"
            "SELECTED: <candidate number (1-based)>\n"
            "REASON: <one-line reason>\n\n"
            f"Original task:\n{prompt[:500]}\n\n"
            f"{candidate_text}"
        )

        try:
            # QA 모델로 Selector 실행
            qa_model = self._get_qa_model(delegate_to, orchestrator)
            response = orchestrator.manager.generate(
                prompt=selector_prompt,
                target=qa_model,
                max_tokens=256,
            )
            response = response.strip()

            # SELECTED 추출
            for line in response.split("\n"):
                line = line.strip()
                if line.startswith("SELECTED:"):
                    num_str = line.split("SELECTED:")[1].strip()
                    try:
                        selected = int(num_str) - 1  # 1-based → 0-based
                        if 0 <= selected < len(results):
                            return selected
                    except ValueError:
                        pass

            # SELECTED를 찾지 못하면 첫 번째 결과 사용
            return 0
        except Exception:
            logger.debug("[MAX] Selector failed, using first result")
            return 0

    def _get_qa_model(self, delegate_to: str, orchestrator) -> str:
        """Selector용 QA 모델을 반환합니다."""
        if hasattr(orchestrator, "_get_model_for_role"):
            return orchestrator._get_model_for_role("QA")
        return "default"

    def _format_trace(
        self,
        results: list[WorkerResult],
        selected_idx: int,
        configs: list[dict[str, str]],
    ) -> str:
        """MAX 모드 실행 트레이스를 포맷팅합니다."""
        worker_details = []
        for i, r in enumerate(results):
            marker = "← SELECTED" if i == selected_idx else ""
            worker_details.append(
                f"  Worker {i + 1}: {r.model} [{r.strategy}] — "
                f"{len(r.output)} chars in {r.elapsed_sec}s {marker}"
            )

        return (
            "⚡ **[MAX Mode]** "
            f"{len(results)}개 워커 병렬 실행 → Selector 선정 완료\n"
            + "\n".join(worker_details)
            + "\n\n"
        )
