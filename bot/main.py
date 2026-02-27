"""Discord TTS Bot - Main bot module for text-to-speech in voice channels."""

from __future__ import annotations

import asyncio

import discord
from discord.ext import commands

from .utils.config import PREFIX, TOKEN, logger
from .utils.queue import set_bot

# Setup intents
intents: discord.Intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

# Create bot instance
bot: commands.Bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Set bot reference for queue module
set_bot(bot)

# List of cogs to load
COGS: list[str] = [
    ".cogs.tts_cog",
    ".cogs.voice_cog",
    ".cogs.join_cog",
    ".cogs.event_cog",
]


async def load_cogs() -> None:
    """Load all cogs."""
    for cog in COGS:
        try:
            await bot.load_extension(cog, package="bot")
            logger.info("Loaded cog: %s", cog)
        except Exception as e:  # noqa: BLE001
            logger.exception("Failed to load cog: %s - %s", cog, e)


async def main() -> None:
    """Main entry point for the bot."""
    async with bot:
        await load_cogs()
        await bot.start(TOKEN)


if __name__ == "__main__":
    asyncio.run(main())
