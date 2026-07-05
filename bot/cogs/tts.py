from typing import TYPE_CHECKING
from typing import cast

import discord
from asgiref.sync import sync_to_async
from discord import app_commands
from discord.ext import commands

from bot.cogs.speaker import SpeakerCog
from bot.services.tts_service import resolve_mentions
from bot.services.tts_service import start_tts_task
from bot.services.voice_service import voice_autocomplete
from bot.ui.multiline_modal import MultilineTTSInputModal
from discord_tts.discord_profiles.interface import get_user_preferences

if TYPE_CHECKING:
    from bot.main import TTSBot


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

        # TODO: Seperate this part out, also in on_message.
        effective_voice = voice
        if effective_voice is None and interaction.user.id:
            prefs = await sync_to_async(get_user_preferences)(
                interaction.user.id,
                interaction.guild_id,
            )
            if prefs.voice:
                effective_voice = prefs.voice.id

        start_tts_task(
            resolved,
            effective_voice,
            interaction.guild_id,
            interaction.channel_id,
        )

        username = interaction.user.display_name

        await interaction.response.send_message(
            f"{username}: {text}",
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

    @app_commands.command(name="stop", description="Stop playback and clear queue")
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop current message and clear queue for channel."""
        if not interaction.guild_id:
            return

        speaker_cog = cast("SpeakerCog", self.bot.get_cog("SpeakerCog"))
        if not speaker_cog:
            await interaction.response.send_message(
                "Speaker service not found.",
                ephemeral=True,
            )
            return

        await speaker_cog.stop_audio(interaction.guild_id)
        await interaction.response.send_message("Stopped and cleared the queue.")

    @app_commands.command(name="skip", description="Skip current voice line")
    async def skip(self, interaction: discord.Interaction) -> None:
        """Skip only the current message."""
        if not interaction.guild_id:
            return

        speaker_cog = cast("SpeakerCog", self.bot.get_cog("SpeakerCog"))

        if not speaker_cog:
            await interaction.response.send_message(
                "Speaker service not found.",
                ephemeral=True,
            )
            return

        success = await speaker_cog.skip_audio(interaction.guild_id)
        if success:
            await interaction.response.send_message("⏭️ Skipped.")
        else:
            await interaction.response.send_message(
                "Nothing is playing right now.",
                ephemeral=True,
            )

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Detect messages from muted people in the bound channels.

        That means people who are self muted, not deafened, and the bound channels are
        the channel the bot was called in with /join and the VC channel.
        """
        if message.author.bot or not message.guild:
            return

        bound_channel_id = self.bot.bound_channels.get(message.guild.id)
        if bound_channel_id is None:
            return

        if not self._bot_in_voice_channel(message.guild):
            return

        member = message.author

        if (
            not isinstance(member, discord.Member)
            or not member.voice
            or not member.voice.self_mute
        ):
            return

        # Check if message is from the bound text channel
        is_bound_text = message.channel.id == bound_channel_id

        # Check if message is from voice channel (VC chat)
        vc = message.guild.voice_client
        is_vc_message = vc and vc.channel and message.channel == vc.channel

        if not is_bound_text and not is_vc_message:
            return

        resolved = resolve_mentions(message.content, message.guild)

        effective_voice = None
        if message.author.id:
            prefs = await sync_to_async(get_user_preferences)(
                message.author.id,
                message.guild.id,
            )
            if prefs.voice:
                effective_voice = prefs.voice.id

        start_tts_task(
            resolved,
            effective_voice,
            message.guild.id,
            message.channel.id,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(TTSCog(bot))
