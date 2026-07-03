from django.conf import settings
from django.db import models


class DiscordUserProfile(models.Model):
    discord_id = models.BigAutoField(primary_key=True)
    user = models.OneToOneField(
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

    def __str__(self) -> str:
        return f"{self.user.username if self.user else 'No user'} - {self.discord_id}"
