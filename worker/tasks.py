import logging
import os
from functools import lru_cache

import scipy.io.wavfile
from celery import shared_task

from apps.voices.models import Voice

from .tts_model import get_model

logger = logging.getLogger(__name__)


@lru_cache(maxsize=4)
def get_cached_voice_state(voice_pk, voice_name):
    """Loads voice state from disk using Django ORM.

    Keeps only the last 4 used voices in memory.
    """
    model = get_model()

    if voice_pk == 0:
        logger.info(
            "Internal voice, using voice name '%s' as audio prompt.",
            voice_name,
        )
        return model.get_state_for_audio_prompt(voice_name)

    try:
        voice = Voice.objects.get(pk=voice_pk)
    except Voice.DoesNotExist:
        logger.warning(
            "Voice pk=%s not found in database, using internal default.",
            voice_pk,
        )
        return model.get_state_for_audio_prompt("alba")

    # Prefer processed safetensor, fall back to audio_source
    if voice.processed_safetensor:
        target_path = voice.processed_safetensor.path
    elif voice.audio_source:
        target_path = voice.audio_source.path
    else:
        logger.warning(
            "Voice pk=%s has no audio file, using internal default.",
            voice_pk,
        )
        return model.get_state_for_audio_prompt("alba")

    logger.info(
        "Loading voice '%s' (pk=%s) into LRU Cache (%s).",
        voice.name,
        voice_pk,
        target_path,
    )
    return model.get_state_for_audio_prompt(target_path)


@shared_task
def generate_tts_task(text, voice_name, voice_pk, output_filename):
    """
    Celery Task: Generates audio and saves to shared volume.
    """
    model = get_model()

    voice_state = get_cached_voice_state(voice_pk, voice_name)

    # Generate Audio. The "." prefix improves prosidy.
    audio_tensor = model.generate_audio(voice_state, "." + text)

    # Save to shared volume
    output_path = os.path.join("/app/shared", output_filename)
    scipy.io.wavfile.write(output_path, model.sample_rate, audio_tensor.cpu().numpy())

    return output_path
