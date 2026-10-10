import json
import logging
import uuid
from functools import lru_cache
from pathlib import Path

import numpy as np
import redis
from celery import shared_task
from django.conf import settings

from discord_tts.voices.models import Voice

from .tts_model import get_model

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.CELERY_BROKER_URL)

STREAM_TTL_SECONDS = 120


@lru_cache(maxsize=4)
def _load_voice_state_cached(target_path: str, mtime: float):
    """Loads voice state from disk or builtin prompt using Pocket-TTS model."""
    model = get_model()
    return model.get_state_for_audio_prompt(target_path)


def reset_voice_cache(voice_pk: int | None = None) -> None:
    """Reset the cached voice state so the bot loads the new safetensors/audio."""
    _load_voice_state_cached.cache_clear()
    logger.info("Reset voice cache (voice_pk=%s)", voice_pk)


def _resolve_target_path(voice: Voice) -> str | None:
    """Finds the path to the processed safetensors or fallback audio source."""
    if voice.processed_safetensor:
        try:
            p = Path(voice.processed_safetensor.path)
            if p.exists():
                return str(p)
        except Exception:
            logger.exception(
                "Error checking processed_safetensor path for voice %s",
                voice.pk,
            )

    if voice.audio_source:
        try:
            p = Path(voice.audio_source.path)
            if p.exists():
                return str(p)
        except Exception:
            logger.exception(
                "Error checking audio_source path for voice %s",
                voice.pk,
            )

    return None


def get_cached_voice_state(voice_pk: int, guild_id: int | None = None):
    """Loads voice state from disk using Django ORM."""
    try:
        voice = Voice.objects.get(pk=voice_pk)
        if guild_id is not None and voice.guild_id not in (0, guild_id):
            logger.warning(
                "Voice pk=%s (guild=%s) is not available in guild %s,"
                " using internal default.",
                voice_pk,
                voice.guild_id,
                guild_id,
            )
            return _load_voice_state_cached("alba", 0.0)
    except Voice.DoesNotExist:
        logger.warning("Voice pk=%s not found, using internal default.", voice_pk)
        return _load_voice_state_cached("alba", 0.0)

    if voice.guild_id == 0:
        return _load_voice_state_cached(voice.name, 0.0)

    target_path = _resolve_target_path(voice)
    if not target_path:
        logger.warning(
            "Voice pk=%s has no audio source, using internal default.",
            voice_pk,
        )
        return _load_voice_state_cached(voice.name, 0.0)

    try:
        mtime = Path(target_path).stat().st_mtime
    except OSError:
        mtime = 0.0

    return _load_voice_state_cached(target_path, mtime)


get_cached_voice_state.cache_clear = reset_voice_cache  # type: ignore[attr-defined]
get_cached_voice_state.cache_info = _load_voice_state_cached.cache_info  # type: ignore[attr-defined]


@shared_task(ignore_result=True)
def generate_tts_task(
    text: str,
    voice_pk: int,
    guild_id: int,
    channel_id: int,
    seq: int = 0,
    syn: bool = False,
):
    """
    Streams audio chunks to Redis as they are generated.
    """
    counter_key = f"guild_line_task_count:{guild_id}"
    stream_key = f"tts_stream:{guild_id}:{uuid.uuid4().hex[:8]}"

    try:
        model = get_model()
        voice_state = get_cached_voice_state(voice_pk, guild_id)

        # Publish control signal FIRST so the bot can set up its pipeline
        payload = {
            "guild_id": guild_id,
            "channel_id": channel_id,
            "stream_key": stream_key,
            "sample_rate": model.sample_rate,
            "channels": 1,
            "seq": seq,
            "syn": syn,
        }

        try:
            redis_client.publish("tts_play_queue", json.dumps(payload))
            logger.info("Published TTS stream signal for guild %i.", guild_id)
        except Exception as e:
            logger.exception("Failed to publish Redis signal", extra={"error": e})
            raise

        # Stream audio chunks as raw PCM with clipping to prevent wrap-around
        for audio_chunk in model.generate_audio_stream(voice_state, text):
            arr = audio_chunk.cpu().numpy()
            pcm_bytes = (
                np.clip(arr * 32767.0, -32768.0, 32767.0).astype("<i2").tobytes()
            )
            redis_client.rpush(stream_key, pcm_bytes)

        # Signal end of stream
        redis_client.rpush(stream_key, b"EOF")
        redis_client.expire(stream_key, STREAM_TTL_SECONDS)

        logger.info(
            "Finished streaming TTS for guild %i, key=%s.",
            guild_id,
            stream_key,
        )

    except Exception:
        # Push EOF on error so the bot's stream doesn't hang
        try:
            redis_client.rpush(stream_key, b"EOF")
            redis_client.expire(stream_key, STREAM_TTL_SECONDS)
        except Exception:
            logger.exception("Failed to push EOF on error for %s", stream_key)
        raise
    finally:
        redis_client.decr(counter_key)
