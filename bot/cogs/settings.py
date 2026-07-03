import discord
from asgiref.sync import sync_to_async
from discord import app_commands
from discord.ext import commands

from apps.discord_profiles.interface import UserPreferenceUpdateData
from apps.discord_profiles.interface import update_user_preferences
from apps.voices.interface import get_available_voices


async def voice_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if not interaction.guild_id:
        e = "guild_id should not be None"
        raise ValueError(e)
    voices = await sync_to_async(get_available_voices)(interaction.guild_id)
    return [app_commands.Choice(name=v.name, value=v.name) for v in voices]


async def update_preferences(
    interaction: discord.Interaction,
    voice: str | None,
    introduce_speaker: int | None,
) -> tuple[bool, str]:
    if not interaction.user.id or not interaction.guild_id:
        e = "user.id and guild_id should not be None"
        raise ValueError(e)

    discord_id = interaction.user.id
    guild_id = interaction.guild_id

    data: UserPreferenceUpdateData = {}

    if voice is not None:
        voices = await sync_to_async(get_available_voices)(guild_id)
        matched_voice = next((v for v in voices if v.name == voice), None)
        if not matched_voice:
            return False, f"Voice '{voice}' not found."
        data["voice_id"] = matched_voice.pk

    if introduce_speaker is not None:
        data["introduce_speaker"] = bool(introduce_speaker)

    return await sync_to_async(update_user_preferences)(
        discord_id,
        guild_id,
        data,
    )


class SettingsCog(commands.Cog):
    """Manage user settings."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="settings", description="Adjust preferences")
    @app_commands.autocomplete(voice=voice_autocomplete)
    @app_commands.describe(
        voice="The voice you want to use",
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
        voice: str | None = None,
        introduce_speaker: int | None = None,
    ) -> None:
        """Adjust TTS preferences."""
        if not voice and not introduce_speaker:
            await interaction.response.send_message(
                "You didn't change anything...",
                ephemeral=True,
            )
            return

        success, message = await update_preferences(
            interaction,
            voice,
            introduce_speaker,
        )
        status = "" if success else "Failed: "
        await interaction.response.send_message(
            f"{status}{message}",
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SettingsCog(bot))
