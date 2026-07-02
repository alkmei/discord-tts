import discord
from discord import app_commands
from discord.ext import commands


class SettingsCog(commands.Cog):
    """Manage user settings."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="settings", description="Adjust preferences")
    async def settings(self, interaction: discord.Interaction) -> None:
        """Send the user an embed that allows editing preferences.

        Currently, they can edit their voice, or toggle the bot introducing the speaker.
        """
