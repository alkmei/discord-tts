import logging
import typing

from django.db import models

logger = logging.getLogger(__name__)

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

    def regenerate_safetensors(self):
        from .tasks import generate_safetensors  # noqa: PLC0415

        if self.audio_source:
            audio_path = self.audio_source.path
            logger.info(
                "Regenerating safetensor for voice '%s' (id=%s, audio=%s)",
                self.name,
                self.pk,
                audio_path,
            )
            generate_safetensors.delay(self.pk, audio_path)
