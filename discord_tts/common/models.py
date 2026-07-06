from django.db import models


class DiscordAccount(models.Model):
    """The central identity for the entire package.

    Links Discord IDs to the package's internal logic.
    """

    discord_id = models.PositiveBigIntegerField(unique=True, db_index=True)

    def __str__(self):
        return f"Discord:{self.discord_id}"
