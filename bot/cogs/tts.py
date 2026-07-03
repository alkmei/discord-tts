import re
from typing import cast

import discord
import emoji
from discord import app_commands
from discord.ext import commands

from bot.cogs.speaker import SpeakerCog
from bot.util import voice_autocomplete
from worker.tasks import generate_tts_task


def clean_tts_text(
    text: str,
    guild: discord.Guild | None,
) -> str:
    """Clean text content for TTS.

    - Replaces URLs with "(insert link here)"
    - Resolves User Mentions to Nicknames
    - Resolves Custom Emojis to their names
    - Resolves Unicode Emojis to spoken words
    """
    content = text

    content = re.sub(r"https?://\S+", "(insert link here)", content)

    # Resolve Mentions <@ID> or <@!ID> to Nicknames
    def replace_mention(match: re.Match[str]) -> str:
        user_id = int(match.group(1))
        if not guild:
            err = "This should not happen in a server"
            raise RuntimeError(err)
        member = guild.get_member(user_id)
        if member:
            return member.display_name
        return "someone"

    content = re.sub(r"<@!?(\d+)>", replace_mention, content)

    # Resolve Custom Emojis <:name:id> or <a:name:id> to "name"
    content = re.sub(r"<a?:([^:]+):\d+>", r" \1 ", content)

    # Resolve Unicode Emojis (🤨 -> face_with_raised_eyebrow)
    # We replace underscores with spaces and remove colons for cleaner TTS
    content = emoji.demojize(content, delimiters=(" ", " "))
    content = content.replace("_", " ").replace(":", "")
    content = " ".join(content.split())

    # Pocket-TTS use to have this bug that cut the first part of a message off.
    # Adding a period was a failsafe, but not sure if that's still needed.
    return "." + content


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
        await interaction.response.send_message("Talking...", ephemeral=True)

    # TODO: This might not work if bulk messages are sent, as every message in the
    # bundle will have the same priority
    async def start_tts_task(
        self,
        guild_id: int,
        channel_id: int,
        text: str,
        voice: int | None,
    ) -> None:
        cleaned = clean_tts_text(text, self.bot.get_guild(guild_id))

        speaker_cog = cast("SpeakerCog", self.bot.get_cog("SpeakerCog"))
        guild_in_progress = (
            speaker_cog
            and guild_id in speaker_cog.playing_tasks
            and not speaker_cog.playing_tasks[guild_id].done()
        )
        priority = 1 if guild_in_progress else 9

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
