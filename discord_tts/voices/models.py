import logging
import typing

from django.db import models
from django.db import transaction

from .validators import audio_extension_validator

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from django.db.models.manager import Manager


class Voice(models.Model):
    name = models.CharField(max_length=32)
    guild_id = models.PositiveBigIntegerField()
    audio_source = models.FileField(
        upload_to="voices/",
        null=True,
        validators=[
            audio_extension_validator,
        ],
    )
    processed_safetensor = models.FileField(
        upload_to="safetensors/",
        null=True,
        blank=True,
    )

    objects: Manager[Voice] = models.Manager()

    def __str__(self) -> str:
        return self.name

    def save(self, *args, **kwargs):
        # Check if this is a new file upload
        is_new_file = False
        if self.pk:
            old_file = Voice.objects.get(pk=self.pk).audio_source
            if self.audio_source and self.audio_source != old_file:
                is_new_file = True
        else:
            is_new_file = True

        super().save(*args, **kwargs)

        # If a new file was uploaded, trigger conversion
        if is_new_file:
            from .tasks import convert_to_ogg_opus  # noqa: PLC0415

            transaction.on_commit(lambda: convert_to_ogg_opus.delay(self.pk))

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
