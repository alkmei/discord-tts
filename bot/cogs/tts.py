import logging
import os

import discord
import redis
from discord import app_commands
from discord.ext import commands

from bot.services.tts_service import clean_tts_text
from bot.services.tts_service import get_priority
from bot.services.voice_service import voice_autocomplete
from worker.tasks import generate_tts_task

logger = logging.getLogger(__name__)

redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))


class TTSCog(commands.Cog):
    """Interface with the TTS."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="say", description="Talk")
    @app_commands.describe(voice="The voice to use", text="The text to say")
    @app_commands.autocomplete(voice=voice_autocomplete)
    async def say(
        self,
        interaction: discord.Interaction,
        text: str,
        voice: int | None,
    ) -> None:
        """Explicitly give bot a message."""
        if not interaction.guild_id:
            await interaction.response.send_message(
                "This command can only be used in servers.",
                ephemeral=True,
            )
            return
        if not interaction.channel_id:
            await interaction.response.send_message(
                "This command needs to be used in a text channel",
                ephemeral=True,
            )
            return

        await self.start_tts_task(
            interaction.guild_id,
            interaction.channel_id,
            text,
            voice,
        )
        await interaction.response.send_message(
            "Talking...",
            ephemeral=True,
            delete_after=5,
        )

    async def start_tts_task(
        self,
        guild_id: int,
        channel_id: int,
        text: str,
        voice: int | None,
    ) -> None:
        cleaned = clean_tts_text(text, self.bot.get_guild(guild_id))

        counter_key = f"guild_line_task_count:{guild_id}"
        current_count_raw = redis_client.get(counter_key)
        current_count = int(current_count_raw) if current_count_raw else 0
        priority = get_priority(current_count)
        logger.info(
            "TTS task queued for guild %s, priority %s (queue_depth=%s)",
            guild_id,
            priority,
            current_count,
        )
        redis_client.incr(counter_key)

        voice_pk = voice or 1
        generate_tts_task.apply_async(
            args=(cleaned, voice_pk, guild_id, channel_id),
            priority=priority,
        )

    @app_commands.command(name="multi", description="Play multiple voicelines")
    async def multi(self, interaction: discord.Interaction):
        """Plays multiple lines with multiple voices"""

    @app_commands.command(name="stop", description="Stop playback")
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop current message and clear queue for channel."""

    @app_commands.command(name="skip", description="Skip current voice line")
    async def skip(self, interaction: discord.Interaction) -> None:
        """Skip the current or next message queued to play for channel."""

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Detect messages from muted people in the bound channels."""


async def setup(bot: commands.Bot):
    await bot.add_cog(TTSCog(bot))
