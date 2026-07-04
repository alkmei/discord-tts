from asgiref.sync import sync_to_async

import discord
from discord import app_commands
from discord.ext import commands

from apps.discord_profiles.interface import get_user_preferences
from bot.services.preferences_service import update_user_voice
from bot.ui.preferences_modal import PreferenceModal
from bot.services.voice_service import voice_autocomplete


class SettingsCog(commands.Cog):
    """Manage user settings."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="voice", description="Change the TTS voice")
    @app_commands.autocomplete(voice=voice_autocomplete)
    @app_commands.describe(
        voice="The voice you want to use",
    )
    async def voice(
        self,
        interaction: discord.Interaction,
        voice: int,
    ) -> None:
        """Change the TTS voice."""
        success, result = await update_user_voice(
            interaction,
            voice=voice,
        )
        if not success:
            await interaction.response.send_message(
                result,
                ephemeral=True,
            )
            return

        message = f"Updated voice to `{result}`."
        await interaction.response.send_message(
            message,
            ephemeral=True,
        )

    @app_commands.command(name="settings", description="Adjust preferences")
    async def settings(
        self,
        interaction: discord.Interaction,
    ) -> None:
        """Adjust TTS preferences."""
        if not interaction.user.id or not interaction.guild_id:
            await interaction.response.send_message(
                "Failed to get preferences",
                ephemeral=True,
            )
            return

        prefs = await sync_to_async(get_user_preferences)(
            interaction.user.id,
            interaction.guild_id,
        )

        await interaction.response.send_modal(PreferenceModal(prefs))


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SettingsCog(bot))
