import os

from celery import shared_task
from django.core.files.base import ContentFile
from pocket_tts import export_model_state

from worker.tasks import get_model

from .models import Voice


@shared_task
def generate_safetensors(voice_id: int, audio_path: str):
    voice = Voice.objects.get(id=voice_id)
    model = get_model()
    model_state_for_voice = model.get_state_for_audio_prompt(audio_path)

    safetensor_path = os.path.join(
        os.path.dirname(audio_path),
        f"{voice.name}_processed.safetensors",
    )
    export_model_state(model_state_for_voice, safetensor_path)

    with open(safetensor_path, "rb") as f:
        voice.processed_safetensor.save(
            f"{voice.name}_processed.safetensors",
            ContentFile(f.read()),
            save=True,
        )

    os.remove(safetensor_path)
