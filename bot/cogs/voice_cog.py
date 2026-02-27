"""Voice Cog - Commands for voice selection and listing."""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from ..utils.config import get_available_voices
from ..utils.db import set_user_voice

if TYPE_CHECKING:
    from discord.ext.commands import Context


class VoiceCog(commands.Cog):
    """Cog for voice selection commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def voice(self, ctx: Context[commands.Bot], name: str) -> None:
        """Set your TTS voice."""
        available: list[str] = get_available_voices()
        name = name.lower()
        if name not in available:
            await ctx.send(f"Voice `{name}` not found. Available: {', '.join(available)}")
            return

        await set_user_voice(ctx.author.id, name)
        await ctx.send(f"Voice set to **{name}**")

    @commands.command()
    async def voices(self, ctx: Context[commands.Bot]) -> None:
        """List available voices."""
        available: list[str] = get_available_voices()
        if not available:
            await ctx.send("No voices available.")
            return
        voice_list: str = "\n".join(available)
        await ctx.send(f"**Available Voices:** \n```\n{voice_list}\n```")


async def setup(bot: commands.Bot) -> None:
    """Load the Voice cog."""
    await bot.add_cog(VoiceCog(bot))
