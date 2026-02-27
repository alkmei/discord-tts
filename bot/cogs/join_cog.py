"""Join Cog - Command for joining voice channels."""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from ..utils.db import set_bound_channel

if TYPE_CHECKING:
    import discord
    from discord.ext.commands import Context


class JoinCog(commands.Cog):
    """Cog for voice channel joining."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def join(self, ctx: Context[commands.Bot]) -> None:
        """Join the voice channel of the command invoker."""
        if not ctx.author.voice:  # type: ignore[union-attr]
            await ctx.send("You are not in a voice channel.")
            return

        channel: discord.VoiceChannel = ctx.author.voice.channel  # type: ignore[union-attr, assignment]
        if ctx.voice_client:
            await ctx.voice_client.move_to(channel)  # type: ignore[union-attr]
        else:
            await channel.connect()

        if ctx.guild:
            await set_bound_channel(ctx.guild.id, ctx.channel.id)  # type: ignore[union-attr]
        await ctx.send(f"Joined **{channel.name}** and bound to this text channel.")


async def setup(bot: commands.Bot) -> None:
    """Load the Join cog."""
    await bot.add_cog(JoinCog(bot))
