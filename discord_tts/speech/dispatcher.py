import logging
import os

import redis

from discord_tts.voices.interface import get_voices_by_name

from .tasks import generate_tts_task
from .utils import clean_tts_text

logger = logging.getLogger(__name__)
redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

_PRIORITY_BRACKETS = [(3, 9), (10, 5)]


def get_priority(count: int) -> int:
    for threshold, priority in _PRIORITY_BRACKETS:
        if count < threshold:
            return priority
    return 1


def dispatch_tts(
    text: str,
    voice_pk: int,
    guild_id: int,
    channel_id: int,
):
    cleaned = clean_tts_text(text)
    counter_key = f"guild_line_task_count:{guild_id}"
    seq_key = f"guild_sequence:{guild_id}"

    current_count_raw = redis_client.get(counter_key)
    current_count = int(current_count_raw) if current_count_raw else 0

    is_syn = current_count == 0
    sequence_number = 0 if is_syn else redis_client.incr(seq_key)

    if is_syn:
        redis_client.set(seq_key, 0)

    priority = get_priority(current_count)
    redis_client.incr(counter_key)

    return generate_tts_task.apply_async(
        args=(cleaned, voice_pk, guild_id, channel_id),
        kwargs={"seq": sequence_number, "syn": is_syn},
        priority=priority,
    )


def handle_multiline_tts(
    raw_text: str,
    guild_id: int,
    discord_id: int,
    channel_id: int,
) -> int:
    """
    Parses "Voice: Text" lines, resolves voices, and dispatches tasks.
    Returns the count of successfully queued lines.
    """
    # Parse raw text into (name, content) pairs
    lines = [line.strip() for line in raw_text.strip().split("\n") if line.strip()]
    parsed_pairs = []
    voice_names = set()

    for line in lines:
        if ":" in line:
            name_part, text_part = line.split(":", 1)
            name = name_part.strip()
            parsed_pairs.append((name, text_part.strip()))
            voice_names.add(name)

    if not parsed_pairs:
        return 0

    voices = get_voices_by_name(
        discord_id=discord_id,
        guild_id=guild_id,
        voice_names=list(voice_names),
    )

    voice_map = {v.name.lower(): v.pk for v in voices}

    queued_count = 0

    for v_name, v_text in parsed_pairs:
        name_key = v_name.lower()

        if name_key in voice_map:
            voice_pk = voice_map[name_key]

            dispatch_tts(
                text=v_text,
                voice_pk=voice_pk,
                guild_id=guild_id,
                channel_id=channel_id,
            )
            queued_count += 1

    return queued_count
