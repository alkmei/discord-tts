import re

import discord
import emoji
from discord import app_commands
from discord.ext import commands


def clean_tts_text(message: discord.Message) -> str:
    """Clean Discord message content for TTS.

    - Replaces URLs with "(insert link here)"
    - Resolves User Mentions to Nicknames
    - Resolves Custom Emojis to their names
    - Resolves Unicode Emojis to spoken words
    """
    content = message.content

    content = re.sub(r"https?://\S+", "(insert link here)", content)

    # Resolve Mentions <@ID> or <@!ID> to Nicknames
    def replace_mention(match: re.Match[str]) -> str:
        user_id = int(match.group(1))
        if not message.guild:
            err = "This should not happen in a server"
            raise RuntimeError(err)
        member = message.guild.get_member(user_id)
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

    # Final cleanup of whitespace
    return " ".join(content.split())


class TTSCog(commands.Cog):
    """Interface with the TTS."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="say", description="Talk")
    @app_commands.describe(voice="The voice to use", text="The text to say")
    async def say(
        self,
        interaction: discord.Interaction,
        voice: str,
        text: str,
    ) -> None:
        """Give bot a message to say."""

    @app_commands.command(name="stop", description="Stop playback")
    async def stop(self, interaction: discord.Interaction) -> None:
        """Stop current message and clear queue for channel."""

    @app_commands.command(name="skip", description="Skip current voice line")
    async def skip(self, interaction: discord.Interaction) -> None:
        """Skip the current or next message queued to play for channel."""
