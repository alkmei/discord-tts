import discord
from discord import app_commands, ui
from discord.ext import commands


class SettingsModal(ui.Modal, title="TTS Preferences"):
    """Modal for settings."""

    voice_select: ui.Label[SettingsModal] = ui.Label(
        text="Select voice",
        description="Please select the voice you want from the list.",
        component=ui.Select(
            placeholder="Select your favorite fruit...",
            required=True,
            options=[
                # TODO: Get voices after implementing voice storage
                discord.SelectOption(label="Apple", value="apple"),
                discord.SelectOption(label="Banana", value="banana"),
                discord.SelectOption(label="Cherry", value="cherry"),
            ],
        ),
    )
    introduce_speaker: ui.Label[SettingsModal] = ui.Label(
        text="Introduce speaker",
        description="Select whether you want the bot to introduce you"
        " (<name> says: [text]).",
        # TODO: Should get existing user preference as default
        component=ui.Checkbox(default=False),
    )

    async def on_submit(self, interaction: discord.Interaction) -> None:
        """Apply settings to user in KV database."""


class SettingsCog(commands.Cog):
    """Manage user settings."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="settings", description="Adjust preferences")
    async def settings(self, interaction: discord.Interaction) -> None:
        """Send the user an embed that allows editing preferences.

        Currently, they can edit their voice, or toggle the bot introducing the speaker.
        """
        await interaction.response.send_modal(SettingsModal())


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SettingsCog(bot))
