import logging
import os
import re
import typing

import emoji
import redis
from asgiref.sync import sync_to_async

from apps.voices.interface import get_voices_by_name
from worker.tasks import generate_tts_task

if typing.TYPE_CHECKING:
    import discord
    from celery.result import AsyncResult


logger = logging.getLogger(__name__)


redis_client = redis.from_url(os.getenv("REDIS_URL", "redis://localhost:6379/0"))

# Priority brackets: (threshold, priority) sorted by threshold ascending
_PRIORITY_BRACKETS = [(3, 9), (10, 5)]


def get_priority(count: int) -> int:
    for threshold, priority in _PRIORITY_BRACKETS:
        if count < threshold:
            return priority
    return 1


def resolve_mentions(text: str, guild: discord.Guild) -> str:
    """Replace Discord user mentions with display names."""

    def replace_mention(match: re.Match[str]) -> str:
        user_id = int(match.group(1))
        member = guild.get_member(user_id)
        if member:
            return member.display_name
        return "someone"

    return re.sub(r"<@!?(\d+)>", replace_mention, text)


def start_tts_task(
    text: str,
    voice: int | None,
    guild_id: int,
    channel_id: int,
) -> AsyncResult:
    cleaned = clean_tts_text(text)
    counter_key = f"guild_line_task_count:{guild_id}"
    seq_key = f"guild_sequence:{guild_id}"

    current_count_raw = redis_client.get(counter_key)
    current_count = int(current_count_raw) if current_count_raw else 0

    # Logic: If no tasks are currently in flight, this is a SYN (Start)
    is_syn = current_count == 0

    if is_syn:
        sequence_number = 0
        redis_client.set(seq_key, 0)
    else:
        sequence_number = redis_client.incr(seq_key)

    logger.debug(
        "[DISPATCHER] Guild %s | Task Count: %s | SYN: %s | SEQ: %s",
        guild_id,
        current_count,
        is_syn,
        sequence_number,
    )

    priority = get_priority(current_count)
    redis_client.incr(counter_key)

    voice_pk = voice or 1
    return generate_tts_task.apply_async(
        args=(cleaned, voice_pk, guild_id, channel_id),
        kwargs={"seq": sequence_number, "syn": is_syn},
        priority=priority,
    )


def clean_tts_text(text: str) -> str:
    """Clean text content for TTS.

    - Replaces URLs with "(insert link here)"
    - Resolves Custom Emojis to their names
    - Resolves Unicode Emojis to spoken words
    """
    content = text

    content = re.sub(r"https?://\S+", "(insert link here)", content)

    # Resolve Custom Emojis <:name:id> or <a:name:id> to "name"
    content = re.sub(r"<a?:([^:]+):\d+>", r" \1 ", content)

    # Resolve Unicode Emojis (🤨 -> face_with_raised_eyebrow)
    # We replace underscores with spaces and remove colons for cleaner TTS
    content = emoji.demojize(content, delimiters=(" ", " "))
    content = content.replace("_", " ").replace(":", "")
    content = " ".join(content.split())

    # Pocket-TTS use to have this bug that cut the first part of a message off.
    # Adding a period was a failsafe, but not sure if that's still needed.
    return "." + content


async def process_multiline_input(text: str, guild_id: int) -> list[tuple[int, str]]:
    """Process the input from the multiline modal

    Input is in format "<voice_name>: <text>" seperated by newline.
    Returns a list of the tuple (voice_id, processed_text)
    """
    lines = [line.strip() for line in text.strip().split("\n") if line.strip()]

    voice_names = []
    for line in lines:
        if ":" in line:
            name_part = line.split(":", 1)[0].strip()
            voice_names.append(name_part)

    voices = await sync_to_async(get_voices_by_name)(
        guild_id=guild_id,
        voice_names=voice_names,
    )

    voice_map = {voice.name.lower(): (voice.pk, voice.name) for voice in voices}
    results: list[tuple[int, str]] = []

    for line in lines:
        if ":" not in line:
            continue

        name_part, text_part = line.split(":", 1)
        voice_name = name_part.strip()

        if voice_name.lower() in voice_map:
            voice_pk, _ = voice_map[voice_name.lower()]
            cleaned = clean_tts_text(text_part.strip())
            results.append((voice_pk, cleaned))

    return results
