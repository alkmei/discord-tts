from django.conf import settings
from django.db import models


class UserPreferences(models.Model):
    # Each preference is tracked per guild
    discord_id = models.BigIntegerField()
    guild_id = models.BigIntegerField()
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
    )

    voice = models.ForeignKey(
        "voices.Voice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    introduce_speaker = models.BooleanField(default=False)
    speak_while_muted = models.BooleanField(default=True)
    echo_say_command = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"{self.user.username if self.user else 'No user'} - {self.discord_id}"
