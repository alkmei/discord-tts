from typing import cast

import discord
from discord import app_commands
from discord.ext import commands

from bot.main import TTSBot
from bot.services.tts_service import resolve_mentions
from bot.services.tts_service import start_tts_task
from bot.services.voice_service import voice_autocomplete
from bot.ui.multiline_modal import MultilineTTSInputModal


class TTSCog(commands.Cog):
    """Interface with the TTS."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = cast("TTSBot", bot)

    def _bot_in_voice_channel(self, guild: discord.Guild) -> bool:
        vc = guild.voice_client
        return vc is not None and vc.channel is not None

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
        if not interaction.guild_id or not interaction.guild:
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

        if not self._bot_in_voice_channel(interaction.guild):
            await interaction.response.send_message(
                "The bot is not in a voice channel.",
                ephemeral=True,
            )
            return

        resolved = resolve_mentions(text, interaction.guild)
        start_tts_task(
            resolved,
            voice,
            interaction.guild_id,
            interaction.channel_id,
        )
        await interaction.response.send_message(
            "Talking...",
            ephemeral=True,
            delete_after=5,
        )

    @app_commands.command(name="multi", description="Play multiple voicelines")
    async def multi(self, interaction: discord.Interaction):
        """Plays multiple lines with multiple voices"""
        if not interaction.guild_id or not interaction.guild:
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

        if not self._bot_in_voice_channel(interaction.guild):
            await interaction.response.send_message(
                "The bot is not in a voice channel.",
                ephemeral=True,
            )
            return

        await interaction.response.send_modal(MultilineTTSInputModal())

    @app_commands.command(name="stop", description="Stop playback")
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop current message and clear queue for channel."""

    @app_commands.command(name="skip", description="Skip current voice line")
    async def skip(self, interaction: discord.Interaction) -> None:
        """Skip the current or next message queued to play for channel."""

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Detect messages from muted people in the bound channels."""
        if message.author.bot:
            return

        if not message.guild:
            return

        bound_channel_id = self.bot.bound_channels.get(message.guild.id)
        if bound_channel_id is None:
            return

        # Check if message is from the bound text channel
        is_bound_text = message.channel.id == bound_channel_id

        # Check if message is from voice channel (VC chat)
        is_vc_message = False
        if self._bot_in_voice_channel(message.guild):
            vc = message.guild.voice_client
            if vc and vc.channel:
                is_vc_message = message.channel == vc.channel

        if not is_bound_text and not is_vc_message:
            return

        resolved = resolve_mentions(message.content, message.guild)
        start_tts_task(
            resolved,
            None,
            message.guild.id,
            message.channel.id,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TTSCog(bot))
