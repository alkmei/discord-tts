from typing import cast

from asgiref.sync import sync_to_async
from discord import Embed
from discord import Interaction
from discord import TextStyle
from discord.ui import Checkbox
from discord.ui import Label
from discord.ui import Modal
from discord.ui import TextInput

from discord_tts.speech.dispatcher import handle_multiline_tts


class MultilineTTSInputModal(Modal):
    text_input: Label[MultilineTTSInputModal] = Label(
        text="Enter your script",
        component=TextInput(
            placeholder="<voice>: <text>\n\n"
            "Example:\nalba: Hello world\nanna: This is a test",
            style=TextStyle.paragraph,
            required=True,
            min_length=1,
            max_length=4000,
        ),
    )
    echo_checkbox: Label[MultilineTTSInputModal] = Label(
        text="Echo text to the server?",
        description="Will send the script into the text channel",
        component=Checkbox(default=True),
    )

    def __init__(self):
        super().__init__(title="Text-to-Speech Input")

    async def on_submit(self, interaction: Interaction):
        echo_to_server = cast("Checkbox", self.echo_checkbox.component).value
        multiline_input = cast("TextInput", self.text_input.component).value
        if not interaction.guild_id or not interaction.channel_id:
            await interaction.response.send_message(
                "Not in a guild or channel",
                ephemeral=True,
                delete_after=20,
            )
            return

        queued_count = await sync_to_async(handle_multiline_tts)(
            raw_text=multiline_input,
            guild_id=interaction.guild_id,
            discord_id=interaction.user.id,
            channel_id=interaction.channel_id,
        )

        await interaction.response.send_message(
            f"Queued {queued_count} message{'s' if queued_count != 1 else ''}!"
            if queued_count
            else "No valid voice lines found",
            ephemeral=True,
        )

        if echo_to_server:
            # The length limit SHOULD be 4096, which is longer than the input
            embed = Embed(
                title="Script",
                description=multiline_input,
                color=0x0099FF,
            )
            await interaction.followup.send(embed=embed)
