from django.db import models


class UserGuildPreferences(models.Model):
    # Each preference is tracked per guild
    account = models.ForeignKey(
        "common.DiscordAccount",
        on_delete=models.CASCADE,
    )
    guild_id = models.BigIntegerField()

    voice = models.ForeignKey(
        "voices.Voice",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    introduce_speaker = models.BooleanField(default=False)
    speak_while_muted = models.BooleanField(default=True)
    echo_say_command = models.BooleanField(default=True)

    objects: models.Manager[UserGuildPreferences] = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["account_id", "guild_id"],
                name="unique_user_per_guild",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.account.discord_id} preferences"
