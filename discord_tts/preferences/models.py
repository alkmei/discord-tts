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
        indexes = [
            models.Index(
                fields=["account", "guild_id"],
                name="user_guild_pref_acc_guild_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["account", "guild_id"],
                name="unique_user_per_guild",
            ),
        ]
        verbose_name = "User Admin Preference"
        verbose_name_plural = "User Admin Preferences"

    def __str__(self) -> str:
        return f"{self.account.discord_id} preferences"


class AdminGuildPreferences(models.Model):
    """Guild-wide preferences

    This does not refer to a discord admin, but a Django admin.
    This model is meant to be changed in the admin interface.
    Will change when bot eventually gets a dashboard.
    """

    guild_id = models.BigIntegerField()

    # If null, then the user has full control. Otherwise, force the option.
    introduce_speaker = models.BooleanField(null=True)
    speak_while_muted = models.BooleanField(null=True)
    echo_say_command = models.BooleanField(null=True)

    objects: models.Manager[AdminGuildPreferences] = models.Manager()

    class Meta:
        verbose_name = "Guild Admin Preference"
        verbose_name_plural = "Guild Admin Preferences"

    def __str__(self) -> str:
        return f"Guild {self.guild_id} Preferences"
