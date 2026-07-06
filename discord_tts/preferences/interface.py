from typing import TypedDict

from django.db import transaction

from discord_tts.voices.interface import get_voice

from .models import UserGuildPreferences


class UserPreferenceUpdateData(TypedDict, total=False):
    """
    Represents the valid fields that can be updated for a user.
    """

    introduce_speaker: bool
    speak_while_muted: bool
    echo_say_command: bool


def update_user_preferences(
    discord_id: int,
    guild_id: int,
    data: UserPreferenceUpdateData,
) -> tuple[bool, UserGuildPreferences]:
    """
    Updates non-voice user preferences.
    """
    with transaction.atomic():
        defaults = {k: v for k, v in data.items() if k != "voice_id"}

        if not defaults:
            return True, UserGuildPreferences()

        prefs, _ = UserGuildPreferences.objects.select_related(
            "voice",
        ).update_or_create(
            discord_id=discord_id,
            guild_id=guild_id,
            defaults={"guild_id": guild_id, **defaults},
        )

        return True, prefs


def update_user_voice(
    discord_id: int,
    guild_id: int,
    voice_id: int,
) -> str | None:
    """
    Updates the user's voice selection.
    Returns the voice name on success, None on failure.
    """
    with transaction.atomic():
        voice = get_voice(guild_id, voice_id)
        if not voice:
            return None

        UserGuildPreferences.objects.update_or_create(
            discord_id=discord_id,
            guild_id=guild_id,
            defaults={"guild_id": guild_id, "voice": voice},
        )

        return voice.name


def get_user_preferences(
    discord_id: int,
    guild_id: int,
) -> UserGuildPreferences:
    """
    Returns the user preferences, creating if not exists.
    """
    with transaction.atomic():
        prefs, _ = UserGuildPreferences.objects.select_related("voice").get_or_create(
            discord_id=discord_id,
            defaults={"guild_id": guild_id},
        )
        return prefs
