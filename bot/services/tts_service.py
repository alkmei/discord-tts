import logging
import os
import re
import typing

import emoji
import redis

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
    """Queue a TTS task for generation and playback.

    - Manages the Redis priority queue
    - Dispatches the Celery task
    """
    cleaned = clean_tts_text(text)

    counter_key = f"guild_line_task_count:{guild_id}"
    current_count_raw = redis_client.get(counter_key)
    current_count = int(current_count_raw) if current_count_raw else 0
    priority = get_priority(current_count)
    logger.info(
        "TTS task queued for guild %s, priority %s (queue_depth=%s)",
        guild_id,
        priority,
        current_count,
    )
    redis_client.incr(counter_key)

    voice_pk = voice or 1
    return generate_tts_task.apply_async(
        args=(cleaned, voice_pk, guild_id, channel_id),
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
