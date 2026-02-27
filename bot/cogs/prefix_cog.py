"""Prefix Cog - Commands for speech prefix configuration."""

from __future__ import annotations

from typing import TYPE_CHECKING

from discord.ext import commands

from ..utils.db import get_user_prefix_enabled, set_user_prefix_enabled

if TYPE_CHECKING:
    from discord.ext.commands import Context  # type: ignore[I001]


class PrefixCog(commands.Cog):
    """Cog for speech prefix configuration commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def prefix(self, ctx: Context[commands.Bot], setting: str | None = None) -> None:
        """
        Enable or disable the speech prefix ('<name> says:') for your messages.

        Usage: !prefix [on|off]
        """
        if setting is None:
            # Show current status
            enabled = await get_user_prefix_enabled(ctx.author.id)
            status = "enabled" if enabled else "disabled"
            await ctx.send(f"Speech prefix is currently **{status}** for you.\nUsage: `!prefix on` or `!prefix off`")
            return

        setting = setting.lower()
        if setting == "on":
            await set_user_prefix_enabled(ctx.author.id, enabled=True)
            await ctx.send("Speech prefix **enabled**. Your messages will be spoken as `<name> says: <text>`.")
        elif setting == "off":
            await set_user_prefix_enabled(ctx.author.id, enabled=False)
            await ctx.send("Speech prefix **disabled**. Your messages will be spoken without the prefix.")
        else:
            await ctx.send(
                "Invalid option. Usage: `!prefix on` or `!prefix off`\n"
                "Enable or disable the speech prefix for your voice messages."
            )


async def setup(bot: commands.Bot) -> None:
    """Load the Prefix cog."""
    await bot.add_cog(PrefixCog(bot))
