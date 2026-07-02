import discord
from discord import app_commands
from discord.ext import commands


class VoiceCog(commands.Cog):
    """Control bot state in voice chats."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="join", description="Join the voice channel")
    async def join(self, interaction: discord.Interaction) -> None:
        """Join the bot into a voice channel and bind the bot to a text channel.

        The bot will watch the bound text channel for messages from people who are muted
        and not deafened and automatically speak for them.
        """

    @app_commands.command(name="leave", description="Leave the voice channel")
    async def leave(self, interaction: discord.Interaction) -> None:
        """Clear the queue for the channel and leave."""
