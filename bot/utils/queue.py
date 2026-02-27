"""TTS Queue management for the Discord TTS Bot."""

from __future__ import annotations

import asyncio
import contextlib
import uuid
from typing import TYPE_CHECKING, Any

import discord

from .config import SHARED_DIR, celery_app, logger

if TYPE_CHECKING:
    from collections.abc import Callable
    from pathlib import Path

    from celery.result import AsyncResult
    from discord.ext import commands


# --- State ---
guild_queues: dict[int, asyncio.Queue[TTSRequest]] = {}  # GuildID -> asyncio.Queue
processing_tasks: dict[int, asyncio.Task[None]] = {}  # GuildID -> Task
currently_playing: dict[int, TTSRequest | None] = {}  # GuildID -> TTSRequest

# Bot reference - set by main.py after bot creation
bot: commands.Bot | None = None


def set_bot(bot_instance: commands.Bot) -> None:
    """Set the bot instance for queue processing."""
    global bot  # noqa: PLW0603
    bot = bot_instance


class TTSRequest:
    """Tracks a Celery task and its associated Discord context."""

    task: AsyncResult[Any]
    user_name: str
    text: str
    filepath: Path

    def __init__(self, task: AsyncResult[Any], user_name: str, text: str, filepath: Path) -> None:
        self.task = task
        self.user_name = user_name
        self.text = text
        self.filepath = filepath


async def wait_for_task_completion(task: AsyncResult[Any]) -> None:
    """Wait for a Celery task to complete using asyncio.Event polling."""
    completion_event: asyncio.Event = asyncio.Event()

    async def poll_task() -> None:
        while not task.ready():  # noqa: ASYNC110
            await asyncio.sleep(0.1)
        completion_event.set()

    poll_task_instance: asyncio.Task[None] = asyncio.create_task(poll_task())
    await completion_event.wait()
    poll_task_instance.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await poll_task_instance


async def wait_for_playback_completion(vc: discord.VoiceClient) -> None:
    """Wait for voice client playback to complete using asyncio.Event polling."""
    completion_event: asyncio.Event = asyncio.Event()

    async def poll_playback() -> None:
        while vc.is_playing():  # noqa: ASYNC110
            await asyncio.sleep(0.1)
        completion_event.set()

    poll_task: asyncio.Task[None] = asyncio.create_task(poll_playback())
    await completion_event.wait()
    poll_task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await poll_task


def create_after_playing_callback(
    request_filepath: Path,
    play_done_event: asyncio.Event,
    event_loop: asyncio.AbstractEventLoop,
) -> Callable[[BaseException | None], None]:
    """Create a callback function for after audio playback completes."""

    def after_playing(error: BaseException | None) -> None:
        if request_filepath.exists():
            with contextlib.suppress(OSError):
                request_filepath.unlink()
        event_loop.call_soon_threadsafe(play_done_event.set)
        if error:
            logger.error("Player error: %s", error)

    return after_playing


async def process_queue(guild_id: int) -> None:
    """Background loop that waits for Celery tasks to finish and plays them sequentially."""
    while True:
        request: TTSRequest = await guild_queues[guild_id].get()
        currently_playing[guild_id] = request

        if bot is None:
            currently_playing[guild_id] = None
            guild_queues[guild_id].task_done()
            continue

        guild: discord.Guild | None = bot.get_guild(guild_id)
        vc: discord.VoiceClient | None = guild.voice_client if guild else None  # type: ignore[assignment]

        if not vc:
            currently_playing[guild_id] = None
            guild_queues[guild_id].task_done()
            continue

        try:
            await wait_for_task_completion(request.task)

            if request.task.state == "FAILURE":
                logger.warning("Celery Task failed: %s", request.task.result)
                currently_playing[guild_id] = None
                guild_queues[guild_id].task_done()
                continue

            await wait_for_playback_completion(vc)

            if request.filepath.exists():
                source: discord.FFmpegPCMAudio = discord.FFmpegPCMAudio(str(request.filepath))
                play_done: asyncio.Event = asyncio.Event()

                after_callback: Callable[[BaseException | None], None] = create_after_playing_callback(
                    request.filepath,
                    play_done,
                    bot.loop,
                )

                vc.play(source, after=after_callback)
                await play_done.wait()

        except asyncio.CancelledError:
            logger.info("Queue processing cancelled for guild %d", guild_id)
            raise

        currently_playing[guild_id] = None
        guild_queues[guild_id].task_done()


async def add_to_tts_queue(guild_id: int, user_name: str, text: str, voice_name: str) -> None:
    """Dispatches directly to Celery's queue and tracks the task locally."""
    if guild_id not in guild_queues:
        guild_queues[guild_id] = asyncio.Queue()
        processing_tasks[guild_id] = asyncio.create_task(process_queue(guild_id))

    task_id: str = str(uuid.uuid4())
    filename: str = f"{task_id}.wav"
    filepath: Path = SHARED_DIR / filename

    # Dispatch to Celery IMMEDIATELY. This puts the generation work into Celery's queue.
    task: AsyncResult[Any] = celery_app.send_task(
        "worker.tasks.generate_tts_task",
        args=[text, voice_name, filename],
    )

    # Track the request so the bot knows what order to play them in
    request: TTSRequest = TTSRequest(task, user_name, text, filepath)
    await guild_queues[guild_id].put(request)
