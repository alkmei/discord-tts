import typing

from django.db import models

if typing.TYPE_CHECKING:
    from django.db.models.manager import Manager


class Voice(models.Model):
    name = models.CharField(max_length=32)
    guild_id = models.PositiveBigIntegerField()
    audio_source = models.FileField(upload_to="raw-voices/")
    processed_safetensor = models.FileField(upload_to="voices/", null=True, blank=True)

    objects: Manager[Voice] = models.Manager()

    def __str__(self) -> str:
        return self.name
