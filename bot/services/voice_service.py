import discord
from asgiref.sync import sync_to_async
from discord import app_commands

from discord_tts.voices.interface import get_available_voices


async def voice_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if not interaction.guild_id:
        e = "guild_id should not be None"
        raise ValueError(e)
    voices = await sync_to_async(get_available_voices)(
        interaction.guild_id,
        search=current,
    )
    return [
        app_commands.Choice(
            name=f"{v.name} (System)" if v.guild_id == 0 else v.name,
            value=v.pk,
        )
        for v in voices
    ]
