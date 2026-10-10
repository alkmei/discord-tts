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
    # If empty, voice is server-wide. Else, it's like a whitelist
    allowed_users = models.ManyToManyField(
        "common.DiscordAccount",
        blank=True,
        related_name="exclusive_voices",
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
            old_voice = Voice.objects.filter(pk=self.pk).first()
            if old_voice:
                old_file = old_voice.audio_source
                if self.audio_source and self.audio_source != old_file:
                    is_new_file = True
                    if old_voice.processed_safetensor:
                        old_voice.processed_safetensor.delete(save=False)
                    self.processed_safetensor = None
            else:
                is_new_file = True
        else:
            is_new_file = True

        super().save(*args, **kwargs)

        if is_new_file:
            from discord_tts.speech.tasks import reset_voice_cache  # noqa: PLC0415

            reset_voice_cache(self.pk)

            # If a new file was uploaded, trigger conversion
            if self.guild_id != 0:
                from .tasks import convert_to_ogg_opus  # noqa: PLC0415

                transaction.on_commit(lambda: convert_to_ogg_opus.delay(self.pk))

    def delete(self, *args, **kwargs):
        voice_pk = self.pk
        if self.processed_safetensor:
            self.processed_safetensor.delete(save=False)
        result = super().delete(*args, **kwargs)
        from discord_tts.speech.tasks import reset_voice_cache  # noqa: PLC0415

        reset_voice_cache(voice_pk)
        return result

    def regenerate_safetensors(self):
        if self.guild_id == 0:
            logger.warning(
                "Refusing to regenerate safetensors for built-in voice '%s' (id=%s)",
                self.name,
                self.pk,
            )
            return

        from discord_tts.speech.tasks import reset_voice_cache  # noqa: PLC0415

        from .tasks import generate_safetensors  # noqa: PLC0415

        reset_voice_cache(self.pk)
        if self.audio_source:
            generate_safetensors.delay(self.pk)
