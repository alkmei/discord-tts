from typing import TYPE_CHECKING
from typing import cast

import discord
from discord import VoiceClient
from discord import app_commands
from discord.ext import commands

if TYPE_CHECKING:
    from bot.main import TTSBot


class VoiceCog(commands.Cog):
    """Control bot state in voice chats."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = cast("TTSBot", bot)

    @commands.Cog.listener()
    async def on_voice_state_update(
        self,
        member: discord.Member,
        before: discord.VoiceState,
        after: discord.VoiceState,
    ) -> None:
        """Auto-disconnect when the bot is the only one left in the voice channel."""
        if not member.guild or not member.guild.voice_client:
            return

        vc = cast("VoiceClient", member.guild.voice_client)
        if vc.user and self.bot.user and vc.user.id != self.bot.user.id:
            return

        if after.channel:
            return

        non_bot_users = [
            m for m in (before.channel.members if before.channel else []) if not m.bot
        ]

        if not non_bot_users:
            await vc.disconnect()
            self.bot.bound_channels.pop(member.guild.id, None)

    @app_commands.command(name="join", description="Join the voice channel")
    async def join(self, interaction: discord.Interaction) -> None:
        """Join the bot into a voice channel and bind the bot to a text channel.

        The bot will watch the bound text channel for messages from people who are muted
        and not deafened and automatically speak for them.
        """
        guild = interaction.guild

        if not guild:
            await interaction.response.send_message(
                "This command cannot be used in DMs.",
                ephemeral=True,
            )
            return

        member = cast("discord.Member", interaction.user)

        if not member.voice:
            await interaction.response.send_message(
                "You must be in a voice channel.",
                ephemeral=True,
            )
            return

        channel = member.voice.channel

        if not channel or not interaction.channel_id:
            await interaction.response.send_message(
                "There's no channel...",
                ephemeral=True,
            )
            return

        if guild.voice_client and channel == guild.voice_client.channel:
            await interaction.response.send_message(
                "The bot is already in this voice channel.",
                ephemeral=True,
            )
            return

        # Unjoin any existing voice channel first
        if guild.voice_client:
            await guild.voice_client.disconnect(force=False)

        await channel.connect()
        self.bot.bound_channels[guild.id] = interaction.channel_id
        await interaction.response.send_message(
            f"Joined {channel.mention}!",
        )

    @app_commands.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction) -> None:
        """Clear the queue for the channel and leave."""
        guild = interaction.guild

        if not guild:
            await interaction.response.send_message(
                "This command cannot be used in DMs.",
                ephemeral=True,
            )
            return

        if not guild.voice_client:
            await interaction.response.send_message(
                "The bot is not in a voice channel.",
                ephemeral=True,
            )
            return

        await guild.voice_client.disconnect(force=False)
        self.bot.bound_channels.pop(guild.id, None)
        await interaction.response.send_message("Left the voice channel.")


async def setup(bot: commands.Bot):
    await bot.add_cog(VoiceCog(bot))
