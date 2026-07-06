from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async

from discord_tts.preferences.interface import UserGuildPreferenceDto
from discord_tts.preferences.interface import update_user_preferences
from discord_tts.preferences.interface import (
    update_user_voice as sync_update_user_voice,
)

if TYPE_CHECKING:
    import discord


async def update_preferences(
    interaction: discord.Interaction,
    introduce_speaker: int | None = None,
    speak_while_muted: int | None = None,
    echo_say_command: int | None = None,
) -> tuple[bool, UserGuildPreferenceDto]:
    if not interaction.user.id or not interaction.guild_id:
        e = "user.id and guild_id should not be None"
        raise ValueError(e)

    discord_id = interaction.user.id
    guild_id = interaction.guild_id

    data: UserGuildPreferenceDto = {}

    if introduce_speaker is not None:
        data["introduce_speaker"] = bool(introduce_speaker)
    if speak_while_muted is not None:
        data["speak_while_muted"] = bool(speak_while_muted)
    if echo_say_command is not None:
        data["echo_say_command"] = bool(echo_say_command)

    if not data:
        return True, {}

    success, prefs = await sync_to_async(update_user_preferences)(
        discord_id,
        guild_id,
        data,
    )

    return success, {
        "introduce_speaker": prefs.introduce_speaker,
        "speak_while_muted": prefs.speak_while_muted,
        "echo_say_command": prefs.echo_say_command,
    }


async def update_user_voice(
    interaction: discord.Interaction,
    voice: int,
) -> tuple[bool, str]:
    if not interaction.user.id or not interaction.guild_id:
        e = "user.id and guild_id should not be None"
        raise ValueError(e)

    discord_id = interaction.user.id
    guild_id = interaction.guild_id

    voice_name = await sync_to_async(sync_update_user_voice)(
        discord_id,
        guild_id,
        voice,
    )
    if not voice_name:
        return False, "Voice not found."

    return True, voice_name
