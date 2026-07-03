import asyncio
import contextlib
import json
import os
from pathlib import Path
from typing import TYPE_CHECKING
from typing import Any
from typing import TypedDict

import discord
import redis.asyncio as aioredis
from discord.ext import commands
from discord.voice_client import VoiceClient

from bot.logging import setup_logging

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


logger = setup_logging()

QUEUE_RECONNECT_TIMEOUT = 30


class RedisMessage(TypedDict):
    type: str
    pattern: Any
    channel: str
    data: str | bytes


class SpeakerCog(commands.Cog):
    """Manage sending audio to Discord

    Listens for signals from TTS workers to see when the audio clip is ready
    """

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self.redis_url = os.getenv("REDIS_URL") or "redis://localhost"
        # Stores a queue for every guild: {guild_id: asyncio.Queue}
        self.queues: dict[int, asyncio.Queue[dict[str, Any]]] = {}
        # Tracks which guilds are currently playing audio
        self.playing_tasks: dict[int, asyncio.Task[None]] = {}

    async def cog_load(self) -> None:
        """Start the Redis listener with the cog."""
        self.bot.loop.create_task(self.redis_listener())

    async def redis_listener(self) -> None:
        """Listen for signals from the worker."""
        r = aioredis.from_url(self.redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe("tts_play_queue")

        listener: AsyncIterator[RedisMessage] = pubsub.listen()

        async for message in listener:
            if message["type"] == "message":
                raw_data = message["data"]
                if isinstance(raw_data, (bytes, str)):
                    data: dict[str, Any] = json.loads(raw_data)
                else:
                    continue
                await self.enqueue_audio(data)

    async def enqueue_audio(self, data: dict[str, Any]) -> None:
        """Adds a new audio file to the guild's specific queue."""
        guild_id = int(data["guild_id"])

        if guild_id not in self.queues:
            self.queues[guild_id] = asyncio.Queue()

        await self.queues[guild_id].put(data)

        # If there isn't a 'player' loop running for this guild, start one
        if guild_id not in self.playing_tasks or self.playing_tasks[guild_id].done():
            self.playing_tasks[guild_id] = self.bot.loop.create_task(
                self.play_loop(guild_id),
            )

    async def play_loop(self, guild_id: int) -> None:
        """Continuously plays audio from the queue until it's empty."""
        queue = self.queues[guild_id]

        while not queue.empty():
            data = await queue.get()
            channel_id = int(data["channel_id"])
            file_path = data["file_path"]

            await self.execute_play(guild_id, channel_id, file_path)

    async def execute_play(
        self,
        guild_id: int,
        channel_id: int,
        file_path: str,
    ) -> None:
        """Handles the actual Discord voice playback."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        vc = guild.voice_client
        if not vc:
            channel = self.bot.get_channel(channel_id)
            if channel is None:
                return

            # Pause the queue for specified time to allow bot reconnection
            paused_event = asyncio.Event()
            reconnect_task = self.bot.loop.create_task(
                self._wait_reconnect(guild, paused_event),
            )

            # Wait for reconnection or timeout
            try:
                await asyncio.wait_for(
                    paused_event.wait(),
                    timeout=QUEUE_RECONNECT_TIMEOUT,
                )
                reconnect_task.cancel()
            except TimeoutError:
                # Timeout expired, clear queue and exit
                with contextlib.suppress(KeyError):
                    while not self.queues[guild_id].empty():
                        self.queues[guild_id].get_nowait()
                return

            vc = guild.voice_client

            if not isinstance(vc, VoiceClient) or not vc.is_connected():
                return

        # Play audio and wait for it to finish
        if isinstance(vc, VoiceClient) and not vc.is_playing():
            done = asyncio.Event()

            def after_playing(error: Exception | None) -> None:
                if error:
                    logger.error("Player error", extra={"error": error})
                try:
                    fp = Path(file_path)
                    if fp.exists():
                        fp.unlink()
                except Exception as e:
                    logger.exception(
                        "Failed to delete %s",
                        file_path,
                        extra={"error": e},
                    )
                self.bot.loop.call_soon_threadsafe(done.set)

            vc.play(discord.FFmpegPCMAudio(file_path), after=after_playing)

            await done.wait()

    async def _wait_reconnect(self, guild: discord.Guild, event: asyncio.Event) -> None:
        """Wait for the bot to reconnect to the voice channel."""
        while not event.is_set():
            vc = guild.voice_client
            if isinstance(vc, VoiceClient) and vc.is_connected():
                event.set()
                return
            await asyncio.sleep(10)


async def setup(bot: commands.Bot):
    await bot.add_cog(SpeakerCog(bot))
