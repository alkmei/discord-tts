import json
import logging
import struct
import uuid
from functools import lru_cache

import redis
from celery import shared_task
from django.conf import settings

from discord_tts.voices.models import Voice

from .tts_model import get_model

logger = logging.getLogger(__name__)

redis_client = redis.from_url(settings.CELERY_BROKER_URL)

STREAM_TTL_SECONDS = 120


def _wav_header(
    sample_rate: int,
    num_channels: int = 1,
    bits_per_sample: int = 16,
) -> bytes:
    """Build a WAV header with unknown data length for streaming.

    Sets the data chunk size to 0xFFFFFFFF so FFmpeg keeps reading
    from stdin until EOF rather than stopping after a fixed byte count.
    """
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = 0xFFFFFFFF
    riff_size = 36 + data_size

    return struct.pack(
        "<4sI4s"  # RIFF header
        "4sIHHIIHH"  # fmt chunk
        "4sI",  # data chunk header
        b"RIFF",
        riff_size & 0xFFFFFFFF,
        b"WAVE",
        b"fmt ",
        16,  # fmt chunk size
        1,  # PCM format
        num_channels,
        sample_rate,
        byte_rate,
        block_align,
        bits_per_sample,
        b"data",
        data_size & 0xFFFFFFFF,
    )


@lru_cache(maxsize=4)
def get_cached_voice_state(voice_pk, guild_id=None):
    """Loads voice state from disk using Django ORM."""
    model = get_model()
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
            return model.get_state_for_audio_prompt("alba")
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
            "seq": seq,
            "syn": syn,
        }

        try:
            redis_client.publish("tts_play_queue", json.dumps(payload))
            logger.info("Published TTS stream signal for guild %i.", guild_id)
        except Exception as e:
            logger.exception("Failed to publish Redis signal", extra={"error": e})
            raise

        # Push WAV header as the first chunk
        header = _wav_header(model.sample_rate)
        redis_client.rpush(stream_key, header)

        # Stream audio chunks as they're generated
        for audio_chunk in model.generate_audio_stream(voice_state, text):
            # Convert tensor chunk to raw PCM bytes (16-bit signed int)
            pcm_bytes = (audio_chunk.cpu().numpy() * 32767).astype("<i2").tobytes()
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
