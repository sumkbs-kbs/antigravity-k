"""Event Bus module."""

import asyncio
import inspect
import logging
import os
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

CallbackType = Callable[..., Any] | Callable[..., Awaitable[Any]]


class EventBus:
    """비동기/동기 이벤트 버스 (Pub/Sub).

    Antigravity-K의 단일 동기 루프의 병목을 해소하고,
    다양한 모듈(인지, 로깅, UI)이 이벤트 기반으로 통신할 수 있게 합니다.
    """

    def __init__(self) -> None:
        """Initialize the EventBus."""
        self._subscribers: dict[str, list[CallbackType]] = {}

    def subscribe(self, event_name: str, callback: CallbackType):
        """특정 이벤트에 콜백을 등록합니다."""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        if callback not in self._subscribers[event_name]:
            self._subscribers[event_name].append(callback)
            logger.debug("[EventBus] Subscribed '%s' to '%s'", callback.__name__, event_name)

    def unsubscribe(self, event_name: str, callback: CallbackType):
        """특정 이벤트에서 콜백을 제거합니다."""
        if event_name in self._subscribers and callback in self._subscribers[event_name]:
            self._subscribers[event_name].remove(callback)

    def publish(self, event_name: str, **kwargs):
        """이벤트를 동기적으로 발생시킵니다.

        비동기 콜백은 백그라운드 태스크로 스케줄링됩니다.
        """
        if event_name not in self._subscribers:
            return

        for callback in self._subscribers[event_name]:
            try:
                if inspect.iscoroutinefunction(callback):
                    # 비동기 환경이면 태스크로 실행, 아니면 무시되거나 별도 런루프 필요 (여기선 백그라운드 스케줄 시도)
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(callback(**kwargs))
                    except RuntimeError:
                        # 실행 중인 루프가 없으면 (순수 동기 환경) 동기적으로 실행
                        asyncio.run(callback(**kwargs))
                else:
                    callback(**kwargs)
            except Exception as e:
                logger.error(
                    "[EventBus] Error in callback '%s' for event '%s': %s",
                    callback.__name__,
                    event_name,
                    e,
                    exc_info=True,
                )

    async def publish_async(self, event_name: str, **kwargs):
        """이벤트를 비동기적으로 발생시킵니다."""
        if event_name not in self._subscribers:
            return

        tasks = []
        for callback in self._subscribers[event_name]:
            if inspect.iscoroutinefunction(callback):
                tasks.append(callback(**kwargs))
            else:
                try:
                    callback(**kwargs)
                except Exception as e:
                    logger.error(
                        "[EventBus] Error in sync callback '%s': %s",
                        callback.__name__,
                        e,
                        exc_info=True,
                    )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# 전역 싱글톤 인스턴스
global_event_bus = EventBus()


def attach_persistent_agency(
    controller: Any,
    project_id: str,
    trajectory_id: str = "hooks",
    hook_bus: Any | None = None,
) -> Callable[[Any], None] | None:
    """Attach a durable observation sink to a HookEventBus instance."""
    bus = hook_bus
    if bus is None:
        from antigravity_k.engine.hook_event_bus import get_hook_event_bus

        bus = get_hook_event_bus()
    bindings: set[tuple[int, str, str]] = getattr(bus, "_persistent_agency_bindings", set())
    key = (id(controller), project_id, trajectory_id)
    if key in bindings:
        return None

    def on_hook_event(event: Any) -> None:
        try:
            controller.record_external_event(
                project_id,
                trajectory_id,
                str(getattr(event, "kind", "unknown")),
                getattr(event, "payload", {}),
            )
        except Exception:
            logger.exception("[EventBus] persistent agency event record failed")

    bus.subscribe_all(on_hook_event)
    bindings.add(key)
    setattr(bus, "_persistent_agency_bindings", bindings)
    return on_hook_event


def bridge_to_hook_event_bus(
    project_root: str | None = None,
    persistent_agency: Any | None = None,
):
    """HookEventBus와 글로벌 EventBus를 양방향 브릿지합니다.

    - EventBus.publish() → HookEventBus JSONL 파일에도 기록 (듀얼 싱크)
    - HookEventBus 이벤트 → EventBus 구독자에게도 전달
    """
    try:
        from antigravity_k.engine.hook_event_bus import get_hook_event_bus

        hook_bus = get_hook_event_bus()

        if persistent_agency is None and project_root:
            from antigravity_k.engine.persistent_agency import PersistentAgencyController

            persistent_agency = PersistentAgencyController(project_root)
        if persistent_agency is not None:
            root = str(Path(project_root or os.getcwd()).resolve())
            attach_persistent_agency(persistent_agency, root, hook_bus=hook_bus)

        # EventBus → HookEventBus 듀얼 싱크
        original_publish = global_event_bus.publish

        def dual_publish(event_name: str, **kwargs):
            original_publish(event_name, **kwargs)
            # 파일 기반 영구 기록 (초기화된 경우에만)
            if hook_bus._initialized:
                hook_bus.emit_event(event_name, kwargs)

        setattr(global_event_bus, "publish", dual_publish)

        # HookEventBus → EventBus 브릿지
        def on_hook_event(event):
            kind = event.kind
            payload = event.payload
            original_publish(f"Hook:{kind}", **payload)

        hook_bus.subscribe_all(on_hook_event)

        logger.info("[EventBus] HookEventBus 듀얼 싱크 브릿지 설정 완료")
    except ImportError:
        logger.warning("예외 발생 (silent swallow 제거)", exc_info=True)
    except Exception:
        logger.exception("[EventBus] HookEventBus 브릿지 설정 실패")
