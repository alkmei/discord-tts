"""Web listener for receiving TTS requests via RabbitMQ."""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

import aio_pika

from .config import RABBITMQ_URL, SHARED_DIR, celery_app, logger
from .queue import TTSRequest, guild_queues, process_queue, processing_tasks

if TYPE_CHECKING:
    import discord
    from discord.ext import commands


async def listen_for_web_requests(bot: commands.Bot) -> None:
    """Background task to receive TTS requests from the Web UI via RabbitMQ."""
    connection: aio_pika.abc.AbstractRobustConnection = await aio_pika.connect_robust(RABBITMQ_URL)
    channel: aio_pika.abc.AbstractChannel = await connection.channel()

    # Declare exchange and queue for web TTS requests
    exchange: aio_pika.abc.AbstractExchange = await channel.declare_exchange(
        "web_tts_requests", aio_pika.ExchangeType.FANOUT, durable=True
    )
    rabbitmq_queue: aio_pika.abc.AbstractQueue = await channel.declare_queue("", exclusive=True)
    await rabbitmq_queue.bind(exchange)

    async with rabbitmq_queue.iterator() as queue_iter:
        async for message in queue_iter:
            try:
                async with message.process():
                    data: dict[str, str | int] = json.loads(message.body.decode())
                    guild_id: int = int(data["guild_id"])

                    # Find the guild and check if bot is in a voice channel there
                    guild: discord.Guild | None = bot.get_guild(guild_id)
                    if not guild:
                        logger.warning("Web request ignored: Guild %d not found.", guild_id)
                        continue

                    vc: discord.VoiceClient | None = guild.voice_client  # type: ignore[assignment]
                    if not vc:
                        logger.warning("Web request ignored: Not in a voice channel in %s.", guild.name)
                        continue

                    # Add to queue
                    task_id: str = str(data["task_id"])
                    filename: str = f"web_{task_id}.wav"
                    filepath = SHARED_DIR / filename

                    request: TTSRequest = TTSRequest(
                        task=celery_app.AsyncResult(task_id),
                        user_name=str(data["user_name"]),
                        text=str(data["text"]),
                        filepath=filepath,
                    )

                    if guild_id not in guild_queues:
                        guild_queues[guild_id] = asyncio.Queue()
                        processing_tasks[guild_id] = asyncio.create_task(process_queue(guild_id))

                    await guild_queues[guild_id].put(request)

            except json.JSONDecodeError:
                logger.exception("Web Listener JSON Error")
            except KeyError:
                logger.exception("Web Listener missing key")
