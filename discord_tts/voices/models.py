import logging
import typing

from django.db import models
from django.db import transaction

from .validators import audio_extension_validator

logger = logging.getLogger(__name__)

if typing.TYPE_CHECKING:
    from django.db.models.manager import Manager


def voice_audio_upload_to(instance, filename):
    return f"{instance.guild_id}/voices/{filename}"


def voice_safetensor_upload_to(instance, filename):
    return f"{instance.guild_id}/safetensors/{filename}"


class Voice(models.Model):
    name = models.CharField(max_length=32)
    guild_id = models.PositiveBigIntegerField()
    audio_source = models.FileField(
        upload_to=voice_audio_upload_to,
        null=True,
        validators=[
            audio_extension_validator,
        ],
    )
    processed_safetensor = models.FileField(
        upload_to=voice_safetensor_upload_to,
        null=True,
        blank=True,
    )

    objects: Manager[Voice] = models.Manager()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["name", "guild_id"],
                name="unique_voice_name_per_guild",
            ),
        ]

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
        if is_new_file and self.guild_id != 0:
            from .tasks import convert_to_ogg_opus  # noqa: PLC0415

            transaction.on_commit(lambda: convert_to_ogg_opus.delay(self.pk))

    def regenerate_safetensors(self):
        if self.guild_id == 0:
            logger.warning(
                "Refusing to regenerate safetensors for built-in voice '%s' (id=%s)",
                self.name,
                self.pk,
            )
            return

        from .tasks import generate_safetensors  # noqa: PLC0415

        if self.audio_source:
            generate_safetensors.delay(self.pk)
