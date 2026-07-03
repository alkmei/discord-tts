from django.db import models


class Voice(models.Model):
    name = models.CharField(max_length=32)
    guild_id = models.PositiveBigIntegerField()
    audio_source = models.FileField()
    processed_safetensor = models.FileField(null=True, blank=True)

    def __str__(self) -> str:
        return self.name
