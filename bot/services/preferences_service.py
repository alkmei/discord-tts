import discord
from asgiref.sync import sync_to_async

from apps.discord_profiles.interface import UserPreferenceUpdateData
from apps.discord_profiles.interface import update_user_preferences
from apps.voices.interface import get_voice


async def update_preferences(
    interaction: discord.Interaction,
    voice: int | None,
    introduce_speaker: int | None,
) -> tuple[bool, str]:
    if not interaction.user.id or not interaction.guild_id:
        e = "user.id and guild_id should not be None"
        raise ValueError(e)

    discord_id = interaction.user.id
    guild_id = interaction.guild_id

    data: UserPreferenceUpdateData = {}

    if voice is not None:
        matched_voice = await sync_to_async(get_voice)(guild_id, voice)
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
