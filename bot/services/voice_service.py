import discord
from asgiref.sync import sync_to_async
from discord import app_commands

from discord_tts.preferences.interface import get_user_preferences
from discord_tts.voices.interface import get_available_voices
from discord_tts.voices.interface import get_voice


async def voice_autocomplete(
    interaction: discord.Interaction,
    current: str,
) -> list[app_commands.Choice[str]]:
    if not interaction.guild_id:
        e = "guild_id should not be None"
        raise ValueError(e)
    voices = await sync_to_async(get_available_voices)(
        interaction.user.id,
        interaction.guild_id,
        search=current,
    )
    return [
        app_commands.Choice(
            name=f"{v.name} (System)" if v.guild_id == 0 else v.name,
            value=v.pk,
        )
        for v in voices[:25]
    ]


async def get_effective_voice(
    user_id: int,
    guild_id: int,
    requested_voice: int | None = None,
) -> int | None:
    """Resolve the effective voice ID for a user.

    If a voice is explicitly requested, validate that it is accessible in this
    guild for this user. If invalid, fall back to the user's preferred voice.
    """
    if requested_voice is not None:
        voice = await sync_to_async(get_voice)(user_id, guild_id, requested_voice)
        if voice:
            return voice.pk

    prefs, _ = await sync_to_async(get_user_preferences)(user_id, guild_id)
    return prefs.get("voice_id")
