from django.db import transaction
from django.db.models.signals import post_save
from django.dispatch import receiver

from apps.voices.tasks import generate_safetensors

from .models import Voice


@receiver(post_save, sender=Voice)
def voice_post_save(sender, instance: Voice, created, **kwargs):
    if created and instance.audio_source and not instance.processed_safetensor:
        transaction.on_commit(
            lambda: generate_safetensors.delay(instance.pk, instance.audio_source.path),
        )
