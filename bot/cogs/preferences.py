import discord
from discord import app_commands
from discord.ext import commands

from bot.services.preferences_service import update_preferences
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
        success, message = await update_preferences(
            interaction,
            voice,
            None,
        )
        status = "" if success else "Failed: "
        await interaction.response.send_message(
            f"{status}{message}",
            ephemeral=True,
        )

    @app_commands.command(name="settings", description="Adjust preferences")
    @app_commands.describe(
        introduce_speaker="Whether the bot should introduce you",
    )
    @app_commands.choices(
        introduce_speaker=[
            app_commands.Choice(name="True", value=1),
            app_commands.Choice(name="False", value=0),
        ],
    )
    async def settings(
        self,
        interaction: discord.Interaction,
        introduce_speaker: int | None = None,
    ) -> None:
        """Adjust TTS preferences."""
        if not introduce_speaker:
            await interaction.response.send_message(
                "You didn't change anything...",
                ephemeral=True,
            )
            return

        success, message = await update_preferences(
            interaction,
            None,
            introduce_speaker,
        )
        status = "" if success else "Failed: "
        await interaction.response.send_message(
            f"{status}{message}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SettingsCog(bot))
