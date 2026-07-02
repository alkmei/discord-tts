import os

import discord
import dotenv
from discord.ext import commands

from .logging import setup_logging

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
        intents = discord.Intents.default()
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self) -> None:
        """Load cogs."""
        for filename in os.listdir("./cogs"):
            if filename.endswith(".py"):
                await self.load_extension(f"cogs.{filename[:-3]}")
                logger.info("Loaded cog", extra={"cog": filename})

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
bot.run(TOKEN)
