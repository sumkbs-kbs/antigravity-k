"""Self-Healing Loop for the test harness.

Extracted from ``harness.py``. These classes implement DOM-based self-healing:
on a test failure, they analyze the accessibility tree / DOM to find an
alternative selector and retry. They are independent of the TestHarness runner
and only depend on the data models in ``harness_models.py``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

from antigravity_k.engine.harness_models import TestIntent, TestResult, TestStatus

logger = logging.getLogger("antigravity_k.harness")


class HealingLoop:
    """하네스 엔지니어링의 핵심: Self-Healing Loop.

    1. 실패 감지 → 2. DOM 스냅샷 분석 → 3. 셀렉터 대체 후보 탐색
    → 4. 재시도 → 5. 성공 시 치유 로그 기록
    """

    # 대체 셀렉터 탐색 전략 (우선순위 순)
    SELECTOR_STRATEGIES = [
        "role",  # getByRole — Accessibility Tree 기반
        "label",  # getByLabel — aria-label 기반
        "text",  # getByText — 텍스트 내용 기반
        "testid",  # getByTestId — data-testid 기반
        "css",  # querySelector — CSS 기반 (최후의 수단)
    ]

    def __init__(self, max_attempts: int = 3):
        """Initialize the HealingLoop.

        Args:
            max_attempts: Maximum number of heal-and-retry attempts.

        """
        self.max_attempts = max_attempts
        self.heal_log: list[dict[str, Any]] = []

    async def try_with_healing(
        self,
        action_fn: Callable,
        page,
        context: dict[str, Any],
        intent: TestIntent,
    ) -> TestResult:
        """액션을 실행하되, 실패 시 self-healing을 시도합니다."""
        start = time.time()
        last_error = None

        for attempt in range(self.max_attempts + 1):
            try:
                result_msg = await action_fn(page, context)
                elapsed = (time.time() - start) * 1000

                healed = attempt > 0
                return TestResult(
                    intent_id=intent.id,
                    status=TestStatus.HEALED if healed else TestStatus.PASSED,
                    duration_ms=elapsed,
                    message=result_msg or "OK",
                    healed=healed,
                    heal_details=(f"Attempt {attempt + 1}: {context.get('heal_strategy', 'N/A')}" if healed else None),
                )
            except Exception as e:
                last_error = str(e)
                logger.exception("[HealingLoop] Attempt %s/%s failed", attempt + 1, self.max_attempts + 1)

                if attempt < self.max_attempts:
                    # DOM 분석 → 대체 셀렉터 탐색
                    healed_context = await self._analyze_and_heal(page, context, str(e))
                    if healed_context:
                        context.update(healed_context)
                        continue

        elapsed = (time.time() - start) * 1000
        return TestResult(
            intent_id=intent.id,
            status=TestStatus.FAILED,
            duration_ms=elapsed,
            message=f"All {self.max_attempts + 1} attempts failed: {last_error}",
        )

    async def _analyze_and_heal(
        self,
        page,
        context: dict[str, Any],
        error: str,
    ) -> dict[str, Any] | None:
        """DOM을 분석하여 대체 셀렉터를 찾습니다."""
        try:
            # Accessibility Tree에서 대체 요소 탐색
            snapshot = await page.accessibility.snapshot()
            if not snapshot:
                return None

            original_target = context.get("target_text", "")

            # 텍스트 매칭으로 대체 셀렉터 탐색
            candidates = self._find_candidates(snapshot, original_target)
            if candidates:
                heal_info = {
                    "heal_strategy": f"accessibility_tree_match: {candidates[0]}",
                    "healed_selector": candidates[0],
                }
                self.heal_log.append(
                    {
                        "original": context.get("selector"),
                        "healed": candidates[0],
                        "error": error,
                        "timestamp": time.time(),
                    },
                )
                return heal_info

        except Exception as e:
            logger.exception("Unhandled exception")
            logger.debug("[HealingLoop] DOM analysis failed: %s", e)

        return None

    def _find_candidates(self, node: dict, target_text: str, depth: int = 0) -> list[str]:
        """Accessibility Tree에서 텍스트가 유사한 노드를 재귀적으로 탐색합니다."""
        candidates = []
        name = node.get("name", "")
        role = node.get("role", "")

        if target_text and target_text.lower() in name.lower():
            candidates.append(f"role={role}, name={name}")

        for child in node.get("children", []):
            candidates.extend(self._find_candidates(child, target_text, depth + 1))

        return candidates


class HealingLoopV2(HealingLoop):
    """v2 Self-Healing Loop: SemanticDOMParser + 치유 학습 통합.

    기존 HealingLoop의 텍스트 매칭을 시맨틱 매칭으로 업그레이드:
    1. 실패 → SemanticDOMParser로 현재 DOM 분석
    2. 7단계 전략으로 대체 요소 탐색
    3. 치유 결과를 학습하여 재발 시 즉시 치유
    """

    SELECTOR_STRATEGIES = [
        "heal_memory",  # 이전 치유 패턴 재사용 (학습)
        "semantic_intent",  # SemanticDOMParser 의도 매칭 (NEW)
        "role",  # getByRole — Accessibility Tree 기반
        "label",  # getByLabel — aria-label 기반
        "text",  # getByText — 텍스트 내용 기반
        "bbox",  # Bounding Box 좌표 기반 (NEW)
        "css",  # querySelector — CSS 기반 (최후의 수단)
    ]

    def __init__(self, max_attempts: int = 5):
        """Initialize the HealingLoopV2.

        Args:
            max_attempts: Maximum number of heal-and-retry attempts.

        """
        super().__init__(max_attempts=max_attempts)
        # 치유 학습 메모리: {원본_셀렉터: 치유된_셀렉터}
        self._heal_memory: dict[str, dict[str, Any]] = {}
        self._dom_parser = None

    def _ensure_dom_parser(self):
        if self._dom_parser is None:
            try:
                from antigravity_k.tools.semantic_dom import SemanticDOMParser

                self._dom_parser = SemanticDOMParser()
            except ImportError:
                logger.warning("[HealingV2] SemanticDOMParser unavailable")
        return self._dom_parser

    async def _analyze_and_heal(
        self,
        page,
        context: dict[str, Any],
        error: str,
    ) -> dict[str, Any] | None:
        """v2: 7단계 전략으로 대체 요소를 탐색합니다."""
        original_selector = context.get("selector", "")
        target_text = context.get("target_text", "")

        # 전략 1: 치유 학습 메모리 조회
        if original_selector and original_selector in self._heal_memory:
            memory = self._heal_memory[original_selector]
            heal_info = {
                "heal_strategy": f"heal_memory: {memory['healed']}",
                "selector": memory.get("healed_selector", ""),
                "target_text": memory.get("healed_text", target_text),
            }
            logger.info("[HealingV2] Memory hit: %s → %s", original_selector, memory["healed"])
            return heal_info

        # 전략 2: SemanticDOMParser 의도 매칭
        snapshot = None
        parser = self._ensure_dom_parser()
        if parser and target_text:
            try:
                snapshot = await parser.snapshot_async(page)
                element = parser.find_by_intent(snapshot, target_text)
                if element:
                    heal_info = {
                        "heal_strategy": f'semantic_intent: {element.ref} [{element.role.value}] "{element.display_name}"',  # noqa: E501
                        "selector": element.css_selector,
                        "target_text": element.display_name,
                        "healed_ref": element.ref,
                    }
                    self._record_heal(original_selector, heal_info)
                    return heal_info
            except Exception as e:
                logger.exception("Unhandled exception")
                logger.debug("[HealingV2] Semantic heal failed: %s", e)

        # 전략 3-5: 기존 A11y Tree 기반 (HealingLoop 로직)
        try:
            snapshot_a11y = await page.accessibility.snapshot()
            if snapshot_a11y:
                candidates = self._find_candidates(snapshot_a11y, target_text)
                if candidates:
                    heal_info = {
                        "heal_strategy": f"a11y_tree: {candidates[0]}",
                        "healed_selector": candidates[0],
                    }
                    self._record_heal(original_selector, heal_info)
                    return heal_info
        except Exception as e:
            logger.exception("Unhandled exception")
            logger.debug("[HealingV2] A11y heal failed: %s", e)

        # 전략 6: Bounding Box 좌표 기반 (SemanticDOMParser)
        if parser:
            try:
                if not snapshot:
                    snapshot = await parser.snapshot_async(page)
                # 원본과 가장 유사한 역할의 요소 찾기
                for el in snapshot.interactable_elements():
                    if el.bbox and el.display_name:
                        heal_info = {
                            "heal_strategy": f"bbox: {el.ref} at {el.bbox.to_compact()}",
                            "selector": el.css_selector,
                            "target_text": el.display_name,
                        }
                        return heal_info
            except Exception:
                logger.exception("Unhandled exception")
                pass

        return None

    def _record_heal(self, original: str, heal_info: dict[str, Any]):
        """치유 결과를 학습 메모리에 기록합니다."""
        if original:
            self._heal_memory[original] = {
                "healed": heal_info.get("heal_strategy", "unknown"),
                "healed_selector": heal_info.get("selector", ""),
                "healed_text": heal_info.get("target_text", ""),
                "timestamp": time.time(),
                "count": self._heal_memory.get(original, {}).get("count", 0) + 1,
            }
        self.heal_log.append(
            {
                "original": original,
                "healed": heal_info.get("heal_strategy", ""),
                "timestamp": time.time(),
            },
        )

    def get_heal_stats(self) -> dict[str, Any]:
        """치유 통계를 반환합니다."""
        return {
            "total_heals": len(self.heal_log),
            "memory_entries": len(self._heal_memory),
            "strategies_used": list(set(h.get("healed", "").split(":")[0] for h in self.heal_log)),
            "memory": {
                k: {
                    "healed_to": v["healed"],
                    "count": v["count"],
                }
                for k, v in self._heal_memory.items()
            },
        }
