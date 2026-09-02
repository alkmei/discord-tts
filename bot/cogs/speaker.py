import asyncio
import contextlib
import json
import os
from typing import Any
from typing import TypedDict
from typing import cast

import discord
import redis.asyncio as aioredis
from discord.ext import commands
from discord.voice_client import VoiceClient

from bot.logging import setup_logging
from bot.services.stream import RedisAudioStream

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
        self.queues: dict[int, asyncio.Queue[dict[str, Any]]] = {}
        self.playing_tasks: dict[int, asyncio.Task[None]] = {}
        self.buffers: dict[
            int,
            dict[int, dict[str, Any]],
        ] = {}  # {guild_id: {seq_num: data}}
        self.expected_seq: dict[int, int] = {}  # {guild_id: next_expected_seq}
        self.waiting_for_syn: dict[int, bool] = {}
        self._listener_task: asyncio.Task | None = None

    async def cog_load(self) -> None:
        """Start the Redis listener safely."""
        self._listener_task = asyncio.create_task(self.redis_listener())

    async def cog_unload(self) -> None:
        """Cleanup task when cog is removed or bot reloads."""
        if self._listener_task:
            self._listener_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._listener_task

        # Also cancel all playing loops
        for task in self.playing_tasks.values():
            task.cancel()

    async def redis_listener(self) -> None:
        """Robust listener with automatic reconnection."""
        while not self.bot.is_closed():
            try:
                # Use health_check_interval to prevent Docker from killing idle connections
                r = aioredis.from_url(
                    self.redis_url,
                    decode_responses=True,  # Simplifies JSON handling
                    health_check_interval=30,
                )

                async with r.pubsub() as pubsub:
                    await pubsub.subscribe("tts_play_queue")
                    logger.info("[REDIS] Subscribed to tts_play_queue")

                    async for message in pubsub.listen():
                        if message["type"] == "message":
                            try:
                                data = json.loads(message["data"])
                                await self.enqueue_audio(data)
                            except json.JSONDecodeError:
                                logger.exception("[REDIS] Received invalid JSON")
                            except Exception as e:
                                logger.exception(
                                    "[REDIS] Error processing message: %s",
                                    e,
                                )

            except aioredis.ConnectionError, aioredis.TimeoutError:
                logger.warning("[REDIS] Connection lost. Retrying in 5 seconds...")
                await asyncio.sleep(5)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.exception("[REDIS] Unexpected error: %s", e)
                await asyncio.sleep(5)

    async def enqueue_audio(self, data: dict[str, Any]) -> None:
        guild_id = int(data["guild_id"])
        seq = data.get("seq", 0)
        syn = data.get("syn", False)

        if guild_id not in self.queues:
            self.queues[guild_id] = asyncio.Queue()
            self.buffers[guild_id] = {}
            self.expected_seq[guild_id] = 0
            self.waiting_for_syn[guild_id] = True  # Start by waiting for SYN

        # If we receive a SYN, we reset our sequence tracking
        if syn:
            logger.debug(
                "[PLAYBACK] SYN received. Starting/Resetting Guild %s to SEQ %s",
                guild_id,
                seq,
            )
            self.expected_seq[guild_id] = seq
            self.waiting_for_syn[guild_id] = False

        # Add the incoming data to the buffer regardless
        self.buffers[guild_id][seq] = data

        # If we are still waiting for a SYN but this packet wasn't it,
        # stop here. Do NOT drain the buffer yet.
        if self.waiting_for_syn.get(guild_id, True):
            logger.debug(
                "[PLAYBACK] Holding SEQ %s in buffer. Still waiting for SYN (SEQ 0).",
                seq,
            )
            return

        # Drain buffer into playback queue (TCP-style ordering)
        count = 0
        while self.expected_seq[guild_id] in self.buffers[guild_id]:
            next_data = self.buffers[guild_id].pop(self.expected_seq[guild_id])
            await self.queues[guild_id].put(next_data)
            self.expected_seq[guild_id] += 1
            count += 1

        if count > 0:
            logger.debug(
                "[PLAYBACK] Drained %s items. Next expected: %s",
                count,
                self.expected_seq[guild_id],
            )

        # Ensure play loop is running
        if guild_id not in self.playing_tasks or self.playing_tasks[guild_id].done():
            self.playing_tasks[guild_id] = self.bot.loop.create_task(
                self.play_loop(guild_id),
            )

    async def play_loop(self, guild_id: int) -> None:
        queue = self.queues[guild_id]

        while True:
            # We use a small timeout to see if the queue is truly finished
            try:
                data = await asyncio.wait_for(queue.get(), timeout=2.0)
            except TimeoutError:
                # If the queue is empty AND no more items are in the re-order buffer,
                # we go back into "Waiting for SYN" mode for the next burst.
                if queue.empty() and not self.buffers.get(guild_id):
                    logger.debug(
                        "[PLAYBACK] Guild %s Idle. Re-arming SYN requirement.",
                        guild_id,
                    )
                    self.waiting_for_syn[guild_id] = True
                    break
                continue

            # Play the audio
            channel_id = int(data["channel_id"])
            stream_key = data["stream_key"]
            await self.execute_play(guild_id, channel_id, stream_key)

    async def _cleanup_stream(self, stream_key: str) -> None:
        try:
            r = aioredis.from_url(self.redis_url)
            await r.delete(stream_key)
            await r.aclose()
        except Exception:
            logger.exception("[PLAYBACK] Failed to cleanup stream %s", stream_key)

    async def _reconnect_voice_client(
        self,
        guild: discord.Guild,
        guild_id: int,
        channel_id: int,
        stream_key: str,
    ) -> VoiceClient | None:
        channel = self.bot.get_channel(channel_id)
        if channel is None:
            return None

        paused_event = asyncio.Event()
        reconnect_task = self.bot.loop.create_task(
            self._wait_reconnect(guild, paused_event),
        )
        try:
            await asyncio.wait_for(
                paused_event.wait(),
                timeout=QUEUE_RECONNECT_TIMEOUT,
            )
            reconnect_task.cancel()
        except TimeoutError:
            with contextlib.suppress(KeyError):
                while not self.queues[guild_id].empty():
                    self.queues[guild_id].get_nowait()
            await self._cleanup_stream(stream_key)
            return None

        vc = guild.voice_client
        if not isinstance(vc, VoiceClient) or not vc.is_connected():
            return None
        return vc

    async def execute_play(
        self,
        guild_id: int,
        channel_id: int,
        stream_key: str,
    ) -> None:
        """Handles the actual Discord voice playback."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        vc = guild.voice_client
        if not vc:
            vc = await self._reconnect_voice_client(
                guild,
                guild_id,
                channel_id,
                stream_key,
            )
            if not vc:
                return

        # Play audio and wait for it to finish
        if isinstance(vc, VoiceClient) and not vc.is_playing():
            done = asyncio.Event()
            stream = RedisAudioStream(self.redis_url, stream_key)

            def after_playing(error: Exception | None) -> None:
                if error:
                    logger.error("[PLAYBACK] Player error", extra={"error": error})
                stream.close()
                self.bot.loop.call_soon_threadsafe(done.set)

            vc.play(
                discord.FFmpegPCMAudio(stream, pipe=True),
                after=after_playing,
            )

            await done.wait()

    async def _wait_reconnect(self, guild: discord.Guild, event: asyncio.Event) -> None:
        """Wait for the bot to reconnect to the voice channel."""
        while not event.is_set():
            vc = guild.voice_client
            if isinstance(vc, VoiceClient) and vc.is_connected():
                event.set()
                return
            await asyncio.sleep(10)

    async def skip_audio(self, guild_id: int) -> bool:
        """Skips the currently playing audio."""
        guild = self.bot.get_guild(guild_id)
        if (
            guild
            and guild.voice_client
            and cast("VoiceClient", guild.voice_client).is_playing()
        ):
            # Calling stop() triggers the 'after' callback in execute_play,
            # which closes the stream and sets the 'done' event.
            cast("VoiceClient", guild.voice_client).stop()
            return True
        return False

    async def stop_audio(self, guild_id: int) -> None:
        """Stops current audio and clears all pending queues/buffers."""
        r = aioredis.from_url(self.redis_url)
        keys_to_delete: list[str] = []

        # Clear the playback queue
        if guild_id in self.queues:
            queue = self.queues[guild_id]
            while not queue.empty():
                try:
                    data = queue.get_nowait()
                    keys_to_delete.append(data["stream_key"])
                except asyncio.QueueEmpty:
                    break

        # Clear the re-ordering buffer
        if guild_id in self.buffers:
            keys_to_delete.extend(
                data["stream_key"] for data in self.buffers[guild_id].values()
            )
            self.buffers[guild_id].clear()

        # Batch delete all unconsumed stream keys
        if keys_to_delete:
            try:
                await r.delete(*keys_to_delete)
            except Exception:
                logger.exception("[PLAYBACK] Failed to delete stopped streams")
        await r.aclose()

        # Reset sequencing logic
        self.expected_seq[guild_id] = 0
        self.waiting_for_syn[guild_id] = True

        # Stop the current hardware playback
        guild = self.bot.get_guild(guild_id)
        if guild and guild.voice_client:
            if cast("VoiceClient", guild.voice_client).is_playing():
                cast("VoiceClient", guild.voice_client).stop()


async def setup(bot: commands.Bot):
    await bot.add_cog(SpeakerCog(bot))
