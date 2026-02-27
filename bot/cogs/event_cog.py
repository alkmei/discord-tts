"""Event Cog - Event handlers for the Discord TTS Bot."""

from __future__ import annotations

import discord
from discord.ext import commands

from ..utils.config import PREFIX, logger
from ..utils.db import get_bound_channel, get_user_prefix_enabled, get_user_voice, init_db
from ..utils.queue import add_to_tts_queue
from ..utils.web_listener import listen_for_web_requests


class EventCog(commands.Cog):
    """Cog for event handlers."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.Cog.listener()
    async def on_ready(self) -> None:
        """Called when the bot is ready and connected to Discord."""
        await init_db()
        if self.bot.user:
            logger.info("Logged in as %s", self.bot.user.name)
        self.bot.loop.create_task(listen_for_web_requests(self.bot))

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        """Process incoming messages for auto-TTS."""
        if message.author.bot:
            return

        # Combine prefix and URL check (startswith accepts a tuple)
        if message.content.startswith((PREFIX, "http://", "https://")):
            return

        # Ensure we are in a guild and author is a Member
        if not message.guild or not isinstance(message.author, discord.Member):
            return

        guild_id = message.guild.id

        # Ensure channel is bound
        bound_channel_id = await get_bound_channel(guild_id)
        if bound_channel_id is None or message.channel.id != bound_channel_id:
            return

        # Ensure author is in a voice channel
        voice_state = message.author.voice
        if not voice_state or not voice_state.channel:
            return

        # Ensure bot is in the SAME voice channel
        vc = message.guild.voice_client
        if not isinstance(vc, discord.VoiceClient) or vc.channel != voice_state.channel:
            return

        # Ensure author is actually muted (the trigger for auto-TTS)
        if not (voice_state.self_mute or voice_state.mute):
            return

        voice_name: str = await get_user_voice(message.author.id) or "alba"
        prefix_enabled: bool = await get_user_prefix_enabled(message.author.id)

        if prefix_enabled:
            text_to_say: str = f"{message.author.display_name} says: {message.content}"
        else:
            text_to_say: str = message.content

        await add_to_tts_queue(
            guild_id,
            message.author.display_name,
            text_to_say,
            voice_name,
        )


async def setup(bot: commands.Bot) -> None:
    """Load the Event cog."""
    await bot.add_cog(EventCog(bot))
