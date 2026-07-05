import os

import discord
import django
import dotenv
from discord.ext import commands

from .logging import setup_logging

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings.local")
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
        self.bound_channels: dict[int, int] = {}  # guild_id: text_channel
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        """Manually load the defined extensions."""
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


bot = TTSBot()

if __name__ == "__main__":
    bot.run(TOKEN)
