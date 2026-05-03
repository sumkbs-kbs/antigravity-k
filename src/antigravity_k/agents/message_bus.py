import logging
from typing import Dict, List, Any
from datetime import datetime

logger = logging.getLogger(__name__)

class MessageBus:
    """
    에이전트 간의 통신(Message Passing)을 담당하는 클래스.
    Claude Agent Teams 아키텍처에서 에이전트들이 서로 피드백을 주고받거나
    작업 상태를 업데이트할 때 사용됩니다.
    """
    def __init__(self):
        self.channels: Dict[str, List[Dict[str, Any]]] = {
            "general": []  # 기본 채널
        }
        self.subscribers: Dict[str, List[Any]] = {
            "general": []
        }
        self.callbacks: Dict[str, List[callable]] = {
            "general": []
        }

    def create_channel(self, channel_name: str):
        if channel_name not in self.channels:
            self.channels[channel_name] = []
            self.subscribers[channel_name] = []
            self.callbacks[channel_name] = []
            logger.info(f"Message channel '{channel_name}' created.")

    def subscribe(self, channel_name: str, agent):
        if channel_name not in self.subscribers:
            self.create_channel(channel_name)
        if agent not in self.subscribers[channel_name]:
            self.subscribers[channel_name].append(agent)
            logger.info(f"Agent '{agent.name}' subscribed to '{channel_name}'.")

    def subscribe_callback(self, channel_name: str, callback: callable):
        """특정 채널에 콜백 함수를 등록하여 이벤트 기반 처리를 지원합니다."""
        if channel_name not in self.callbacks:
            self.create_channel(channel_name)
        if callback not in self.callbacks[channel_name]:
            self.callbacks[channel_name].append(callback)
            logger.info(f"Callback registered for channel '{channel_name}'.")

    def publish(self, channel_name: str, sender: str, message: str, meta: Dict[str, Any] = None):
        """특정 채널에 메시지를 발행합니다."""
        if channel_name not in self.channels:
            logger.warning(f"Channel '{channel_name}' does not exist.")
            return

        msg_obj = {
            "timestamp": datetime.now().isoformat(),
            "sender": sender,
            "message": message,
            "meta": meta or {}
        }
        self.channels[channel_name].append(msg_obj)
        logger.debug(f"[{channel_name}] {sender}: {message}")

        # 1. 일반 구독자(에이전트)들에게 메시지 전달
        for agent in self.subscribers[channel_name]:
            # 에이전트의 내부 컨텍스트에 추가
            agent.add_message("user", f"[{sender} via {channel_name}]: {message}")

        # 2. 콜백 구독자들에게 이벤트 전달 (Pub-Sub 콜백 실행)
        for cb in self.callbacks[channel_name]:
            try:
                cb(msg_obj)
            except Exception as e:
                logger.error(f"Error executing callback on channel '{channel_name}': {e}")

    def get_history(self, channel_name: str) -> List[Dict[str, Any]]:
        return self.channels.get(channel_name, [])
