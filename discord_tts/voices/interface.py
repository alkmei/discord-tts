from django.db import models

from discord_tts.voices.models import Voice


def get_available_voices(guild_id: int, search: str = ""):
    """Get a list of available voices per guild

    Searches by name. If empty, show all.
    This includes built in system voices (guild_id=0)
    """
    queryset = Voice.objects.filter(
        models.Q(guild_id=guild_id) | models.Q(guild_id=0),
    )
    if search:
        queryset = queryset.filter(name__icontains=search)
    return list(queryset)


def get_voice(guild_id: int, voice_pk: int):
    """Get a voice by pk.

    Only includes available voices.
    """
    return Voice.objects.filter(
        models.Q(guild_id=guild_id) | models.Q(guild_id=0),
        pk=voice_pk,
    ).first()


def get_voices_by_name(guild_id: int, voice_names: list[str]):
    """Get voices by their names.

    Only include available voices to the user.
    """
    return list(
        Voice.objects.filter(
            models.Q(guild_id=guild_id) | models.Q(guild_id=0),
            name__in=voice_names,
        ),
    )
