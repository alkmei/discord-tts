import asyncio
import contextlib
import os
import signal
from typing import cast

import discord
import django
import dotenv
from discord.ext import commands

from .logging import setup_logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django.setup()

dotenv.load_dotenv()

logger = setup_logging()

TOKEN = os.getenv("DISCORD_BOT_TOKEN")

# Raise an error if missing
if not TOKEN:
    error = (
        "DISCORD_BOT_TOKEN not found in environment variables."
        " Please create a .env file or set the environment variable."
    )
    raise ValueError(error)


class TTSBot(commands.Bot):
    """TTSBot entry point."""

    def __init__(self) -> None:
        self.EXTENSIONS: list[str] = [
            "bot.cogs.voice",
            "bot.cogs.tts",
            "bot.cogs.preferences",
            "bot.cogs.speaker",
        ]
        intents = discord.Intents.default()
        intents.voice_states = True
        self.bound_channels: dict[int, int] = {}  # guild_id: text_channel
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        """Manually load the defined extensions."""
        loop = asyncio.get_running_loop()
        with contextlib.suppress(NotImplementedError):
            # When SIGTERM is received, trigger self.close()
            # Doesn't work for Windows I think.
            loop.add_signal_handler(
                signal.SIGTERM,
                lambda: asyncio.create_task(self.close()),
            )
        for extension in self.EXTENSIONS:
            try:
                await self.load_extension(extension)
                logger.info("Successfully loaded extension: %s", extension)
            except commands.ExtensionError:
                logger.exception("Failed to load extension: %s", extension)

    async def on_ready(self) -> None:
        """Sync slash commands."""
        if not self.user:
            err = "This shouldn't happen unless there isn't a user for the bot"
            raise RuntimeError(err)
        logger.info(
            "Logged in as %s (ID: %i)",
            self.user,
            self.user.id,
        )
        await self.tree.sync()

    async def cleanup(self) -> None:
        """Disconnect from all voice channels."""
        logger.info("Disconnecting...")
        for guild in self.guilds:
            if guild.voice_client:
                with contextlib.suppress(Exception):
                    await cast("discord.VoiceClient", guild.voice_client).disconnect()

    async def close(self):
        await self.cleanup()
        await super().close()


bot = TTSBot()

if __name__ == "__main__":
    bot.run(TOKEN)
