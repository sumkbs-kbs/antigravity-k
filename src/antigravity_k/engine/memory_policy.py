"""
Antigravity-K: 메모리 정책 엔진 (Memory Policy)
=================================================
LRU 기반 모델 메모리 관리 정책을 캡슐화합니다.
ModelManager의 _ensure_memory 로직을 분리하여 테스트 용이성과 확장성을 높입니다.

사용법:
    policy = MemoryPolicy(max_gb=48.0, cooldown_sec=60, auto_unload=True)
    policy.ensure_memory(needed_gb=8.0, loaded_models=manager._loaded, unload_fn=manager.unload)
    policy.evict_unused(loaded_models=manager._loaded, unload_fn=manager.unload, idle_sec=300)
"""

from __future__ import annotations

import logging
import time
from typing import Callable, Dict, Any

logger = logging.getLogger("antigravity_k.memory_policy")


class MemoryPolicy:
    """LRU 기반 모델 메모리 관리 정책.

    Attributes:
        max_gb: 최대 허용 메모리 (GB)
        cooldown_sec: 언로드 쿨다운 (초)
        auto_unload: 자동 언로드 활성화 여부
        idle_eviction_sec: 유휴 모델 자동 퇴출 기준 시간 (초), 데몬에서 사용
    """

    def __init__(
        self,
        max_gb: float = 48.0,
        cooldown_sec: float = 60.0,
        auto_unload: bool = True,
        idle_eviction_sec: float = 300.0,
    ):
        self.max_gb = max_gb
        self.cooldown_sec = cooldown_sec
        self.auto_unload = auto_unload
        self.idle_eviction_sec = idle_eviction_sec

    def current_usage_gb(self, loaded_models: Dict[str, Any]) -> float:
        """현재 로드된 모델의 총 메모리 사용량(GB)을 반환합니다."""
        return sum(getattr(m, "actual_memory_gb", 0.0) for m in loaded_models.values())

    def ensure_memory(
        self,
        needed_gb: float,
        loaded_models: Dict[str, Any],
        unload_fn: Callable[[str], bool],
    ) -> None:
        """필요한 메모리를 확보합니다. LRU 순서로 모델을 언로드합니다.

        Args:
            needed_gb: 확보해야 할 메모리 (GB)
            loaded_models: {model_name: LoadedModel} 딕셔너리
            unload_fn: 모델 언로드 함수 (model_name -> bool)

        Raises:
            MemoryError: 충분한 메모리를 확보할 수 없을 때
        """
        if not self.auto_unload:
            return

        current_used = self.current_usage_gb(loaded_models)
        available = self.max_gb - current_used

        if available >= needed_gb:
            return

        # LRU: last_used_at 기준 오래된 모델부터 언로드
        sorted_models = sorted(
            list(loaded_models.items()),
            key=lambda x: getattr(x[1], "last_used_at", 0),
        )

        for name, loaded in sorted_models:
            if available >= needed_gb:
                break

            elapsed_sec = time.time() - getattr(loaded, "last_used_at", 0)
            mem_gb = getattr(loaded, "actual_memory_gb", 0.0)

            if elapsed_sec < self.cooldown_sec:
                logger.warning(
                    f"[{name}] 쿨다운({self.cooldown_sec}초) 경과 전이지만 "
                    f"메모리 부족으로 강제 언로드 시도 (경과: {elapsed_sec:.1f}초)"
                )
            else:
                logger.info(f"[{name}] 메모리 확보를 위해 자동 언로드 ({mem_gb}GB)")

            available += mem_gb
            unload_fn(name)

        if available < needed_gb:
            raise MemoryError(
                f"메모리 부족: 필요 {needed_gb}GB, "
                f"사용 가능 {available:.1f}GB "
                f"(한도 {self.max_gb}GB)"
            )

    def evict_unused(
        self,
        loaded_models: Dict[str, Any],
        unload_fn: Callable[[str], bool],
        idle_sec: float | None = None,
    ) -> list[str]:
        """유휴 시간이 초과된 모델을 퇴출합니다.

        Args:
            loaded_models: {model_name: LoadedModel} 딕셔너리
            unload_fn: 모델 언로드 함수
            idle_sec: 유휴 판정 기준 (초), None이면 self.idle_eviction_sec 사용

        Returns:
            퇴출된 모델 이름 리스트
        """
        threshold = idle_sec if idle_sec is not None else self.idle_eviction_sec
        now = time.time()
        evicted: list[str] = []

        # dict가 반복 중 변경되므로 리스트로 미리 복사
        for name, loaded in list(loaded_models.items()):
            last_used = getattr(loaded, "last_used_at", 0)
            if now - last_used > threshold:
                mem_gb = getattr(loaded, "actual_memory_gb", 0.0)
                logger.info(
                    f"[MemoryPolicy] 유휴 모델 퇴출: {name} "
                    f"(idle {now - last_used:.0f}s > {threshold}s, {mem_gb}GB)"
                )
                unload_fn(name)
                evicted.append(name)

        return evicted
