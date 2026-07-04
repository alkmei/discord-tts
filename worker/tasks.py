import json
import logging
import uuid
from functools import lru_cache
from pathlib import Path

import redis
import scipy.io.wavfile
from celery import shared_task
from django.conf import settings

from apps.voices.models import Voice

from .tts_model import get_model

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.CELERY_BROKER_URL)


@lru_cache(maxsize=4)
def get_cached_voice_state(voice_pk):
    """Loads voice state from disk using Django ORM."""
    model = get_model()
    try:
        voice = Voice.objects.get(pk=voice_pk)
    except Voice.DoesNotExist:
        logger.warning("Voice pk=%s not found, using internal default.", voice_pk)
        return model.get_state_for_audio_prompt("alba")

    if voice.guild_id == 0:
        return model.get_state_for_audio_prompt(voice.name)

    if voice.processed_safetensor:
        target_path = voice.processed_safetensor.path
    elif voice.audio_source:
        target_path = voice.audio_source.path
    else:
        logger.warning(
            "Voice pk=%s has no audio source, using internal default.",
            voice_pk,
        )
        return model.get_state_for_audio_prompt(voice.name)
    return model.get_state_for_audio_prompt(target_path)


@shared_task(ignore_result=True)
def generate_tts_task(text: str, voice_pk: int, guild_id: int, channel_id: int):
    """
    Generates audio, saves to shared volume, and signals the bot.
    """
    counter_key = f"guild_line_task_count:{guild_id}"

    try:
        model = get_model()
        voice_state = get_cached_voice_state(voice_pk)

        audio_tensor = model.generate_audio(voice_state, text)

        filename = f"{guild_id}_{channel_id}_{uuid.uuid4().hex[:8]}.wav"
        output_path = Path(settings.TTS_SHARED_DIR) / filename

        scipy.io.wavfile.write(output_path, model.sample_rate, audio_tensor.cpu().numpy())

        payload = {
            "guild_id": guild_id,
            "channel_id": channel_id,
            "file_path": str(output_path),
        }

        try:
            redis_client.publish("tts_play_queue", json.dumps(payload))
            logger.info("Published TTS signal for guild %i to Redis.", guild_id)
        except Exception as e:
            logger.exception("Failed to publish Redis signal", extra={"error": e})
            output_path.unlink(missing_ok=True)
            raise
    finally:
        redis_client.decr(counter_key)
