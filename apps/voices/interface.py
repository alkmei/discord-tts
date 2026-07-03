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
