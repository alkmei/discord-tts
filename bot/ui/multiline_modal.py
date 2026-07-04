from typing import cast

from discord import TextStyle
from discord.ui import Checkbox
from discord.ui import Label
from discord.ui import Modal
from discord.ui import TextInput


class TTSInputModal(Modal):
    text_input: Label[TTSInputModal] = Label(
        text="Enter your TTS messages",
        component=TextInput(
            placeholder="<voice>: <text>\n<voice>: <text>\n\n"
            "Example:\nalba: Hello world\nanna: This is a test",
            style=TextStyle.paragraph,
            required=True,
            min_length=1,
            max_length=2000,
        ),
    )
    echo_checkbox: Label[TTSInputModal] = Label(
        text="Do you want the text to be echoed into the server?",
        component=Checkbox(),
    )

    def __init__(self):
        super().__init__(title="Text-to-Speech Input")
        self.echo_to_server = False

    async def on_submit(self, interaction):
        self.echo_to_server = cast("Checkbox", self.echo_checkbox.component).value
        await interaction.response.send_message("Input received!", ephemeral=True)
