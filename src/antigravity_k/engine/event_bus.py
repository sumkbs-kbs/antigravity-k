import asyncio
import logging
from typing import Callable, Dict, List, Any, Awaitable, Union

logger = logging.getLogger(__name__)

CallbackType = Union[Callable[..., Any], Callable[..., Awaitable[Any]]]


class EventBus:
    """
    비동기/동기 이벤트 버스 (Pub/Sub)
    Antigravity-K의 단일 동기 루프의 병목을 해소하고,
    다양한 모듈(인지, 로깅, UI)이 이벤트 기반으로 통신할 수 있게 합니다.
    """

    def __init__(self):
        self._subscribers: Dict[str, List[CallbackType]] = {}

    def subscribe(self, event_name: str, callback: CallbackType):
        """특정 이벤트에 콜백을 등록합니다."""
        if event_name not in self._subscribers:
            self._subscribers[event_name] = []
        if callback not in self._subscribers[event_name]:
            self._subscribers[event_name].append(callback)
            logger.debug(
                f"[EventBus] Subscribed '{callback.__name__}' to '{event_name}'"
            )

    def unsubscribe(self, event_name: str, callback: CallbackType):
        """특정 이벤트에서 콜백을 제거합니다."""
        if (
            event_name in self._subscribers
            and callback in self._subscribers[event_name]
        ):
            self._subscribers[event_name].remove(callback)

    def publish(self, event_name: str, **kwargs):
        """
        이벤트를 동기적으로 발생시킵니다.
        비동기 콜백은 백그라운드 태스크로 스케줄링됩니다.
        """
        if event_name not in self._subscribers:
            return

        for callback in self._subscribers[event_name]:
            try:
                if asyncio.iscoroutinefunction(callback):
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
                    f"[EventBus] Error in callback '{callback.__name__}' for event '{event_name}': {e}",
                    exc_info=True,
                )

    async def publish_async(self, event_name: str, **kwargs):
        """
        이벤트를 비동기적으로 발생시킵니다.
        """
        if event_name not in self._subscribers:
            return

        tasks = []
        for callback in self._subscribers[event_name]:
            if asyncio.iscoroutinefunction(callback):
                tasks.append(callback(**kwargs))
            else:
                try:
                    callback(**kwargs)
                except Exception as e:
                    logger.error(
                        f"[EventBus] Error in sync callback '{callback.__name__}': {e}",
                        exc_info=True,
                    )

        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)


# 전역 싱글톤 인스턴스
global_event_bus = EventBus()


def bridge_to_hook_event_bus():
    """HookEventBus와 글로벌 EventBus를 양방향 브릿지합니다.

    - EventBus.publish() → HookEventBus JSONL 파일에도 기록 (듀얼 싱크)
    - HookEventBus 이벤트 → EventBus 구독자에게도 전달
    """
    try:
        from antigravity_k.engine.hook_event_bus import get_hook_event_bus

        hook_bus = get_hook_event_bus()

        # EventBus → HookEventBus 듀얼 싱크
        original_publish = global_event_bus.publish

        def dual_publish(event_name: str, **kwargs):
            original_publish(event_name, **kwargs)
            # 파일 기반 영구 기록 (초기화된 경우에만)
            if hook_bus._initialized:
                hook_bus.emit_event(event_name, kwargs)

        global_event_bus.publish = dual_publish

        # HookEventBus → EventBus 브릿지
        def on_hook_event(event):
            kind = event.kind
            payload = event.payload
            original_publish(f"Hook:{kind}", **payload)

        hook_bus.subscribe_all(on_hook_event)

        logger.info("[EventBus] HookEventBus 듀얼 싱크 브릿지 설정 완료")
    except ImportError:
        logger.debug("[EventBus] HookEventBus 미설치 — 듀얼 싱크 비활성")
    except Exception as e:
        logger.warning(f"[EventBus] HookEventBus 브릿지 설정 실패: {e}")
