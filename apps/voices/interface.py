from django.db import models

from apps.voices.models import Voice


def get_available_voices(guild_id: int):
    """Get a list of available voices per guild

    This includes built in system voices (guild_id=0)
    """
    return list(
        Voice.objects.filter(
            guild_id=guild_id,
        )
        | Voice.objects.filter(
            guild_id=0,
        ),
    )


def get_voice(guild_id: int, voice_pk: int):
    """Get a voice by pk.

    Only includes available voices.
    """
    return Voice.objects.filter(
        models.Q(guild_id=guild_id) | models.Q(guild_id=0),
        pk=voice_pk,
    )
