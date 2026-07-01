"""Discord Bot module."""

import asyncio
import logging

logger = logging.getLogger("antigravity_k.integrations.discord")

try:
    import discord
except ImportError:
    discord = None


class DiscordBotClient:
    """Antigravity-K Discord Integration.

    디스코드 채널에서 멘션되면 Orchestrator를 통해 AI 응답을 생성하여 반환합니다.
    """

    def __init__(self, token: str, registry, target_model: str = "deepseek-r1:70b"):
        """Initialize the DiscordBotClient.

        Args:
            token (str): str token.
            registry: registry.
            target_model (str): str target model.

        """
        self.token = token
        self.registry = registry  # SlashCommandRegistry or Orchestrator
        self.target_model = target_model

        if discord is None:
            logger.error("discord.py is not installed.")
            return

        intents = discord.Intents.default()
        intents.message_content = True
        self.client = discord.Client(intents=intents)

        @self.client.event
        async def on_ready():
            logger.info("Discord Bot logged in as %s", self.client.user)

        @self.client.event
        async def on_message(message):
            # Ignore self
            if message.author == self.client.user:
                return

            # Respond only if mentioned
            if self.client.user in message.mentions:
                content = message.content.replace(f"<@{self.client.user.id}>", "").strip()
                if not content:
                    return

                async with message.channel.typing():
                    try:
                        # Antigravity-K registry 처리
                        # 비동기 환경에서 동기 함수 실행 (예시)
                        result = await asyncio.to_thread(self.registry.execute, content)

                        # Discord 메시지 길이 제한(2000자) 우회 (Chunking)
                        if len(result) > 2000:
                            chunks = [result[i : i + 1900] for i in range(0, len(result), 1900)]
                            for chunk in chunks:
                                await message.reply(chunk)
                        else:
                            await message.reply(result)
                    except Exception as e:
                        logger.exception("Error handling discord message")
                        await message.reply(f"❌ 오류가 발생했습니다: {str(e)}")

    def run(self):
        """Run."""
        if not discord:
            print("Please install discord.py")
            return
        if not self.token:
            print("Discord token is required.")
            return
        self.client.run(self.token)


if __name__ == "__main__":
    # Test runner
    print("This script is a module. Import DiscordBotClient to run.")
