import discord
from discord import app_commands
from discord.ext import commands

from bot.services.preferences_service import update_preferences
from bot.services.preferences_service import update_user_voice
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
    @app_commands.describe(
        introduce_speaker="Whether the bot should introduce you",
        speak_while_muted="Whether the bot should speak while you are muted",
        echo_say_command="Whether the bot should echo the !say command",
    )
    @app_commands.choices(
        introduce_speaker=[
            app_commands.Choice(name="True", value=1),
            app_commands.Choice(name="False", value=0),
        ],
        speak_while_muted=[
            app_commands.Choice(name="True", value=1),
            app_commands.Choice(name="False", value=0),
        ],
        echo_say_command=[
            app_commands.Choice(name="True", value=1),
            app_commands.Choice(name="False", value=0),
        ],
    )
    async def settings(
        self,
        interaction: discord.Interaction,
        introduce_speaker: int | None = None,
        speak_while_muted: int | None = None,
        echo_say_command: int | None = None,
    ) -> None:
        """Adjust TTS preferences."""
        success, result = await update_preferences(
            interaction,
            introduce_speaker=introduce_speaker,
            speak_while_muted=speak_while_muted,
            echo_say_command=echo_say_command,
        )
        if not success:
            await interaction.response.send_message(
                "Failed",
                ephemeral=True,
            )
            return

        prefs = result
        message_parts = []
        if introduce_speaker is not None:
            intro_text = (
                "Will now introduce you"
                if prefs.introduce_speaker
                else "Will no longer introduce you"
            )
            message_parts.append(intro_text)
        if speak_while_muted is not None:
            muted_text = (
                "Will now speak while muted"
                if prefs.speak_while_muted
                else "Will no longer speak while muted"
            )
            message_parts.append(muted_text)
        if echo_say_command is not None:
            echo_text = (
                "Will now echo the /say command"
                if prefs.echo_say_command
                else "Will no longer echo the /say command"
            )
            message_parts.append(echo_text)
        if message_parts:
            if len(message_parts) == 1:
                message = f"{message_parts[0]}."
            else:
                message = (
                    f"{', '.join(message_parts[:-1])}, and {message_parts[-1].lower()}."
                )
        else:
            message = "No changes made."

        await interaction.response.send_message(
            message,
            ephemeral=True,
        )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(SettingsCog(bot))
