from typing import cast

import discord
from asgiref.sync import sync_to_async
from discord import app_commands
from discord import ui
from discord.ext import commands

from apps.voices.interface import get_available_voices


class SettingsModal(ui.Modal, title="TTS Preferences"):
    """Modal for settings."""

    voice_select: ui.Label[SettingsModal] = ui.Label(
        text="Select voice",
        description="Please select the voice you want from the list.",
        component=ui.Select(
            placeholder="Select your favorite voice...",
            required=True,
        ),
    )
    introduce_speaker: ui.Label[SettingsModal] = ui.Label(
        text="Introduce speaker",
        description="Select whether you want the bot to introduce you"
        " (<name> says: [text]).",
        # TODO: Should get existing user preference as default
        component=ui.Checkbox(default=False),
    )

    def __init__(self, voices):
        super().__init__()
        cast("ui.Select", self.voice_select.component).options = [
            discord.SelectOption(label=v.name, value=str(v.pk)) for v in voices
        ]

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Apply settings to user in database."""
        await interaction.response.send_message("Settings saved!", ephemeral=True)


class SettingsCog(commands.Cog):
    """Manage user settings."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="settings", description="Adjust preferences")
    async def settings(self, interaction: discord.Interaction) -> None:
        """Send the user an embed that allows editing preferences.

        Currently, they can edit their voice, or toggle the bot introducing the speaker.
        """
        voices = await sync_to_async(get_available_voices)(interaction.guild_id)
        modal = SettingsModal(voices)
        await interaction.response.send_modal(modal)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SettingsCog(bot))
