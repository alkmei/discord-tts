"""Discord TTS Bot - Main bot module for text-to-speech in voice channels."""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable

    from celery.result import AsyncResult
    from discord.ext.commands import Context  # type: ignore[import]

import aio_pika
import discord
from celery import Celery
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv()

import os

# --- Configuration ---
TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "")
PREFIX: str = "!"
VOICES_DIR: Path = Path("/app/voices")
SHARED_DIR: Path = Path("/app/shared")

# Constants for queue display
TEXT_PREVIEW_LENGTH: int = 50
MAX_QUEUE_DISPLAY: int = 10

celery_app: Celery = Celery("tts_worker", broker=RABBITMQ_URL, backend="rpc://")

intents: discord.Intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot: commands.Bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)

# --- State ---
user_voice_selections: dict[int, str] = {}  # UserID -> Voice Name
bound_channels: dict[int, int] = {}  # GuildID -> ChannelID
guild_queues: dict[int, asyncio.Queue[TTSRequest]] = {}  # GuildID -> asyncio.Queue
processing_tasks: dict[int, asyncio.Task[None]] = {}  # GuildID -> Task
currently_playing: dict[int, TTSRequest | None] = {}  # GuildID -> TTSRequest


def get_available_voices() -> list[str]:
    """Returns list of available voice names from voices directory."""
    voices: list[str] = []
    if VOICES_DIR.exists():
        for filepath in VOICES_DIR.iterdir():
            ext: str = filepath.suffix
            name: str = filepath.stem
            if ext in [".safetensors", ".wav"]:
                voices.append(name.lower())
    return voices


# --- Queue Logic ---


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


async def listen_for_web_requests() -> None:
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
                    filepath: Path = SHARED_DIR / filename

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


# --- Events ---
@bot.event
async def on_ready() -> None:
    """Called when the bot is ready and connected to Discord."""
    if bot.user:
        logger.info("Logged in as %s", bot.user.name)
    bot.loop.create_task(listen_for_web_requests())


@bot.event
async def on_message(message: discord.Message) -> None:
    """Process incoming messages for commands and auto-TTS."""
    if message.author.bot:
        return
    await bot.process_commands(message)
    if message.content.startswith(PREFIX):
        return

    if message.content.startswith("https://") or message.content.startswith("http://"):
        return

    # Auto-TTS logic
    if (
        message.guild
        and message.guild.id in bound_channels
        and message.channel.id == bound_channels[message.guild.id]
        and message.author.voice  # type: ignore[union-attr]
        and message.author.voice.channel  # type: ignore[union-attr]
    ):
        vc: discord.VoiceClient | None = message.guild.voice_client  # type: ignore[assignment]
        author_voice: discord.VoiceState = message.author.voice  # type: ignore[union-attr, assignment]
        if vc and vc.channel == author_voice.channel and (author_voice.self_mute or author_voice.mute):
            voice_name: str = user_voice_selections.get(message.author.id, "alba")
            text_to_say: str = f"{message.author.display_name} says: {message.content}"
            await add_to_tts_queue(
                message.guild.id,
                message.author.display_name,
                text_to_say,
                voice_name,
            )


# --- Commands ---


@bot.command()
async def join(ctx: Context[commands.Bot]) -> None:
    """Join the voice channel of the command invoker."""
    if not ctx.author.voice:  # type: ignore[union-attr]
        await ctx.send("You are not in a voice channel.")
        return

    channel: discord.VoiceChannel = ctx.author.voice.channel  # type: ignore[union-attr, assignment]
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)  # type: ignore[union-attr]
    else:
        await channel.connect()

    if ctx.guild:
        bound_channels[ctx.guild.id] = ctx.channel.id  # type: ignore[union-attr]
    await ctx.send(f"Joined **{channel.name}** and bound to this text channel.")


@bot.command()
async def queue(ctx: Context[commands.Bot]) -> None:
    """Displays the items currently waiting in the queue (Plaintext)."""
    if not ctx.guild:
        await ctx.send("This command must be used in a server.")
        return

    guild_id: int = ctx.guild.id

    # Get current and queued items
    current: TTSRequest | None = currently_playing.get(guild_id)

    # Access internal queue list safely
    queue_list: list[TTSRequest] = (
        list(guild_queues[guild_id]._queue) if guild_id in guild_queues else []  # type: ignore[attr-defined] # noqa: SLF001
    )

    if not current and not queue_list:
        await ctx.send("The queue is currently empty.")
        return

    lines: list[str] = ["**TTS Queue**"]

    # 1. Currently Playing section
    if current:
        status: str = "Playing" if current.task.ready() else "Generating"
        # Truncate text to TEXT_PREVIEW_LENGTH chars to prevent hitting message limits
        text_preview: str = (
            current.text[:TEXT_PREVIEW_LENGTH] + "..." if len(current.text) > TEXT_PREVIEW_LENGTH else current.text
        )
        lines.append(f"__Now:__ **{current.user_name}** ({status}): {text_preview}")

    # 2. Up Next section
    if queue_list:
        lines.append("\n__Up Next:__")
        for i, req in enumerate(queue_list[:MAX_QUEUE_DISPLAY], 1):
            status = "Ready" if req.task.ready() else "Queued"
            text_preview = req.text[:TEXT_PREVIEW_LENGTH] + "..." if len(req.text) > TEXT_PREVIEW_LENGTH else req.text
            lines.append(f"{i}. **{req.user_name}** [{status}]: {text_preview}")

        if len(queue_list) > MAX_QUEUE_DISPLAY:
            lines.append(f"...and {len(queue_list) - MAX_QUEUE_DISPLAY} more.")
    elif current:
        lines.append("\n(No other items pending)")

    # Send as a standard message
    await ctx.send("\n".join(lines))


@bot.command()
async def t(ctx: Context[commands.Bot], *, text: str) -> None:
    """Say text with username prefix."""
    if not ctx.voice_client:
        await ctx.send("Use `!join` first.")
        return

    if not ctx.guild:
        await ctx.send("This command must be used in a server.")
        return

    voice_name: str = user_voice_selections.get(ctx.author.id, "alba")
    text_to_say: str = f"{ctx.author.display_name} says: {text}"
    await add_to_tts_queue(ctx.guild.id, ctx.author.display_name, text_to_say, voice_name)


@bot.command()
async def s(ctx: Context[commands.Bot], *, text: str) -> None:
    """Say text without username prefix."""
    if not ctx.voice_client:
        await ctx.send("Use `!join` first.")
        return

    if not ctx.guild:
        await ctx.send("This command must be used in a server.")
        return

    voice_name: str = user_voice_selections.get(ctx.author.id, "alba")
    await add_to_tts_queue(ctx.guild.id, ctx.author.display_name, text, voice_name)


@bot.command()
async def multi(ctx: Context[commands.Bot], *, text: str) -> None:
    """Say multiple lines with optional voice prefixes."""
    if not ctx.voice_client:
        await ctx.send("Use `!join` first.")
        return

    if not ctx.guild:
        await ctx.send("This command must be used in a server.")
        return

    # For each line, if it starts with valid_voice:, use that voice for the line
    lines: list[str] = text.splitlines()
    for line in lines:
        if ":" in line:
            potential_voice, actual_text = line.split(":", 1)
            potential_voice = potential_voice.strip().lower()
            if potential_voice in get_available_voices():
                voice_name: str = potential_voice
                text_to_say: str = actual_text.strip()
                await add_to_tts_queue(ctx.guild.id, ctx.author.display_name, text_to_say, voice_name)
                continue

        # If no valid voice prefix, use default
        voice_name = user_voice_selections.get(ctx.author.id, "alba")
        text_to_say = line.strip()
        await add_to_tts_queue(ctx.guild.id, ctx.author.display_name, text_to_say, voice_name)


@bot.command()
async def stop(ctx: Context[commands.Bot]) -> None:
    """Stop playback and clear the queue."""
    if ctx.voice_client:
        ctx.voice_client.stop()  # type: ignore[union-attr]

        # Clear the local queue AND cancel the pending tasks in Celery!
        if ctx.guild and ctx.guild.id in guild_queues:
            while not guild_queues[ctx.guild.id].empty():
                try:
                    req: TTSRequest = guild_queues[ctx.guild.id].get_nowait()
                    # Tell Celery to kill the task if it hasn't started or is running
                    celery_app.control.revoke(req.task.id, terminate=True)
                    guild_queues[ctx.guild.id].task_done()
                except asyncio.QueueEmpty:
                    break

    await ctx.send("Stopped playback and cancelled pending tasks.")


@bot.command()
async def voice(ctx: Context[commands.Bot], name: str) -> None:
    """Set your TTS voice."""
    available: list[str] = get_available_voices()
    name = name.lower()
    if name not in available:
        await ctx.send(f"Voice `{name}` not found. Available: {', '.join(available)}")
        return

    user_voice_selections[ctx.author.id] = name
    await ctx.send(f"Voice set to **{name}**")


@bot.command()
async def voices(ctx: Context[commands.Bot]) -> None:
    """List available voices."""
    available: list[str] = get_available_voices()
    if not available:
        await ctx.send("No voices available.")
        return
    voice_list: str = "\n".join(available)
    await ctx.send(f"**Available Voices:** \n```\n{voice_list}\n```")


if __name__ == "__main__":
    bot.run(TOKEN)
