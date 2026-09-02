from typing import TypedDict

from django.db import transaction

from discord_tts.common.interface import sync_discord_account
from discord_tts.voices.interface import get_voice

from .models import AdminGuildPreferences
from .models import UserGuildPreferences


class UserGuildPreferenceDto(TypedDict, total=False):
    """Represents the valid fields that can be updated for a user.

    NOTE: These NEED to match with preference modal!
    """

    introduce_speaker: bool
    speak_while_muted: bool
    echo_say_command: bool
    voice_id: int


def update_user_preferences(
    discord_id: int,
    guild_id: int,
    data: UserGuildPreferenceDto,
) -> tuple[bool, UserGuildPreferences]:
    """
    Updates non-voice user preferences.
    """
    account, _ = sync_discord_account(discord_id)

    with transaction.atomic():
        defaults = {k: v for k, v in data.items() if k != "voice_id"}

        if not defaults:
            return True, UserGuildPreferences()

        prefs, _ = UserGuildPreferences.objects.select_related(
            "voice",
        ).update_or_create(
            account=account,
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
    account, _ = sync_discord_account(discord_id)

    with transaction.atomic():
        voice = get_voice(discord_id, guild_id, voice_id)
        if not voice:
            return None

        UserGuildPreferences.objects.update_or_create(
            account=account,
            guild_id=guild_id,
            defaults={"guild_id": guild_id, "voice": voice},
        )

        return voice.name


def get_user_preferences(
    discord_id: int,
    guild_id: int,
) -> tuple[UserGuildPreferenceDto, UserGuildPreferenceDto]:
    """Gets or creates the user preferences.

    Returns the user's preferences and admin override.
    """
    account, _ = sync_discord_account(discord_id)

    with transaction.atomic():
        prefs, _ = UserGuildPreferences.objects.select_related("voice").get_or_create(
            account=account,
            guild_id=guild_id,
            defaults={"guild_id": guild_id},
        )
        admin_prefs, _ = AdminGuildPreferences.objects.get_or_create(
            guild_id=guild_id,
            defaults={"guild_id": guild_id},
        )

        result: UserGuildPreferenceDto = {
            "introduce_speaker": prefs.introduce_speaker,
            "speak_while_muted": prefs.speak_while_muted,
            "echo_say_command": prefs.echo_say_command,
        }

        admin_res: UserGuildPreferenceDto = {}
        if admin_prefs.introduce_speaker is not None:
            admin_res["introduce_speaker"] = admin_prefs.introduce_speaker
        if admin_prefs.speak_while_muted is not None:
            admin_res["speak_while_muted"] = admin_prefs.speak_while_muted
        if admin_prefs.echo_say_command is not None:
            admin_res["echo_say_command"] = admin_prefs.echo_say_command
        if prefs.voice:
            result["voice_id"] = prefs.voice.id
        return result, admin_res
