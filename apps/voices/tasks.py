import logging
from pathlib import Path

from celery import shared_task
from django.core.files.base import ContentFile
from pocket_tts import export_model_state

from worker.tasks import get_model

from .models import Voice

logger = logging.getLogger(__name__)


@shared_task
def generate_safetensors(voice_id: int, audio_path: str):
    logger.info(
        "Starting safetensor regeneration for voice_id=%s, audio=%s",
        voice_id,
        audio_path,
    )
    voice = Voice.objects.get(id=voice_id)
    model = get_model()
    model_state_for_voice = model.get_state_for_audio_prompt(audio_path)

    safetensor_path = Path(audio_path).parent / f"{voice.name}_{voice_id}.safetensors"
    export_model_state(model_state_for_voice, str(safetensor_path))

    with Path(safetensor_path).open("rb") as f:
        voice.processed_safetensor.save(
            f"{voice.name}_processed.safetensors",
            ContentFile(f.read()),
            save=True,
        )

    Path(safetensor_path).unlink()
    logger.info(
        "Safetensor regeneration complete for voice '%s' (id=%s)",
        voice.name,
        voice_id,
    )
