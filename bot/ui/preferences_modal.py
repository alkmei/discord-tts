from typing import cast

from discord import Interaction
from discord.ui import Checkbox
from discord.ui import Label
from discord.ui import Modal

from bot.services.preferences_service import update_preferences
from discord_tts.preferences.interface import UserGuildPreferenceDto as PrefsDto


class PreferenceModal(Modal):
    introduce_speaker: Label[PreferenceModal] = Label(
        text="Introduce speaker",
        description="Whether the bot should introduce you",
        component=Checkbox(),
    )
    speak_while_muted: Label[PreferenceModal] = Label(
        text="Speak while muted",
        description="Whether the bot should speak while you are muted",
        component=Checkbox(),
    )
    echo_say_command: Label[PreferenceModal] = Label(
        text="Echo /say command",
        description="Whether the bot should repeat "
        "what you said for the rest of the class",
        component=Checkbox(),
    )

    def __init__(self, prefs: PrefsDto, admin_prefs: PrefsDto):
        self._set_defaults(prefs, admin_prefs)
        super().__init__(title="Preferences")

    def _set_defaults(self, prefs: PrefsDto, admin_prefs: PrefsDto) -> None:
        keys = ["introduce_speaker", "speak_while_muted", "echo_say_command"]

        for key in keys:
            label = getattr(self, key)

            admin_val = admin_prefs.get(key)
            if admin_val is not None:
                label.text = f"{label.text} ({admin_val})"
                label.description = f"{label.description} (controlled by admin)"

            component = cast("Checkbox", label.component)
            component.default = bool(prefs.get(key, False))

    async def on_submit(self, interaction: Interaction):
        if not interaction.guild_id:
            await interaction.response.send_message(
                "Not in a guild",
                ephemeral=True,
                delete_after=20,
            )
            return

        introduce_speaker = cast("Checkbox", self.introduce_speaker.component).value
        speak_while_muted = cast("Checkbox", self.speak_while_muted.component).value
        echo_say_command = cast("Checkbox", self.echo_say_command.component).value

        success, result = await update_preferences(
            interaction,
            introduce_speaker=introduce_speaker,
            speak_while_muted=speak_while_muted,
            echo_say_command=echo_say_command,
        )

        if not success:
            await interaction.response.send_message(
                str(result),
                ephemeral=True,
                delete_after=20,
            )
            return

        message_parts = []
        if introduce_speaker is not None:
            intro_text = (
                "Will now introduce you"
                if result.get("introduce_speaker")
                else "Will no longer introduce you"
            )
            message_parts.append(intro_text)
        if speak_while_muted is not None:
            muted_text = (
                "Will now speak while muted"
                if result.get("speak_while_muted")
                else "Will no longer speak while muted"
            )
            message_parts.append(muted_text)
        if echo_say_command is not None:
            echo_text = (
                "Will now echo the /say command"
                if result.get("echo_say_command")
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
            delete_after=20,
        )
