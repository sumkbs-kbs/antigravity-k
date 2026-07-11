"""Slack Bot module."""

import asyncio
import logging

logger = logging.getLogger("antigravity_k.integrations.slack")

try:
    from slack_bolt.adapter.socket_mode.async_handler import AsyncSocketModeHandler
    from slack_bolt.async_app import AsyncApp
except ImportError:
    AsyncApp = None  # type: ignore


class SlackBotClient:
    """Antigravity-K Slack Integration.

    Socket Mode를 사용하여 슬랙 채널의 멘션 이벤트에 응답합니다.
    """

    def __init__(self, bot_token: str, app_token: str, registry):
        """Initialize the SlackBotClient.

        Args:
            bot_token (str): str bot token.
            app_token (str): str app token.
            registry: registry.

        """
        self.bot_token = bot_token
        self.app_token = app_token
        self.registry = registry

    def _init_app(self):
        """Slack 앱을 초기화합니다 (slack_bolt가 설치된 경우에만)."""
        # type: ignore[truthy-function]
        if AsyncApp is None:
            logger.error("slack_bolt or slack_sdk is not installed.")
            return None

        app = AsyncApp(token=self.bot_token)

        @app.event("app_mention")
        async def handle_app_mention(event, say):
            text = event.get("text", "")
            # Remove mention format like <@U012345>
            import re

            content = re.sub(r"<@[A-Z0-9]+>", "", text).strip()

            if not content:
                return

            try:
                # Antigravity-K 처리
                result = await asyncio.to_thread(self.registry.execute, content)
                await say(result)
            except Exception as e:
                logger.exception("Error handling slack mention")
                await say(f"❌ 오류가 발생했습니다: {str(e)}")

        return app

    async def run_async(self):
        """Run async."""
        if not AsyncApp:
            print("Please install slack_bolt and slack_sdk")
            return
        app = self._init_app()
        if app is None:
            return
        handler = AsyncSocketModeHandler(app, self.app_token)
        await handler.start_async()

    def run(self):
        """Start the Slack bot and block until stopped."""
        asyncio.run(self.run_async())


if __name__ == "__main__":
    print("This script is a module. Import SlackBotClient to run.")
