from django.db import models

from discord_tts.common.interface import sync_discord_account
from discord_tts.voices.models import Voice


def _get_accessible_voice_queryset(discord_id: int, guild_id: int):
    """
    Helper to get the base queryset for voices accessible by a specific user.
    """
    account, _ = sync_discord_account(discord_id)

    guild_filter = models.Q(guild_id=guild_id) | models.Q(guild_id=0)

    # (Public/No whitelist OR User is in whitelist)
    permission_filter = models.Q(allowed_users__isnull=True) | models.Q(
        allowed_users=account,
    )

    # Use .distinct() because M2M joins can sometimes return duplicate rows
    return Voice.objects.filter(guild_filter & permission_filter).distinct()


def get_available_voices(discord_id: int, guild_id: int, search: str = ""):
    """Get a list of available voices per guild, respecting user whitelists."""
    queryset = _get_accessible_voice_queryset(discord_id, guild_id)

    if search:
        queryset = queryset.filter(name__icontains=search)

    return list(queryset)


def get_all_guild_voices(guild_id: int):
    """Get list per guild, no user whitelist"""
    return list(
        Voice.objects.filter(models.Q(guild_id=guild_id) | models.Q(guild_id=0)),
    )


def get_voice(discord_id: int, guild_id: int, voice_pk: int):
    """Get a specific voice, ensuring the user has permission to see it."""
    return (
        _get_accessible_voice_queryset(discord_id, guild_id).filter(pk=voice_pk).first()
    )


def get_voices_by_name(discord_id: int, guild_id: int, voice_names: list[str]):
    """Get voices by name, ensuring only accessible ones are returned."""
    return list(
        _get_accessible_voice_queryset(discord_id, guild_id).filter(
            name__in=voice_names,
        ),
    )
