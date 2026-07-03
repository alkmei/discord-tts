from typing import TypedDict

from django.db import models
from django.db import transaction

from apps.voices.models import Voice

from .models import UserPreferences


class UserPreferenceUpdateData(TypedDict, total=False):
    """
    Represents the valid fields that can be updated for a user.
    """

    voice_id: int
    introduce_speaker: bool


def update_user_preferences(
    discord_id: int,
    guild_id: int,
    data: UserPreferenceUpdateData,
) -> tuple[bool, str]:
    """
    Updates user preferences.
    """
    try:
        with transaction.atomic():
            prefs, _ = UserPreferences.objects.get_or_create(
                discord_id=discord_id,
                defaults={"guild_id": guild_id},
            )

            voice_id = data.get("voice_id")
            if voice_id is not None:
                voice = Voice.objects.filter(
                    models.Q(guild_id=guild_id) | models.Q(guild_id=0),
                    pk=voice_id,
                ).first()

                if not voice:
                    return False, f"Voice {voice_id} is not available in this server."
                prefs.voice = voice

            intro = data.get("introduce_speaker")
            if intro is not None:
                prefs.introduce_speaker = intro

            prefs.save()
            return True, "Success"

    except Exception as e:
        return False, str(e)
