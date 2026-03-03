import json

import discord
from discord.ext import commands
from celery import Celery
import asyncio
import os
import uuid
from dotenv import load_dotenv
import redis.asyncio as aioredis
from . import database

load_dotenv()

# --- Configuration ---
TOKEN = os.getenv("DISCORD_BOT_TOKEN")
REDIS_URL = os.getenv("REDIS_URL")
PREFIX = "!"
VOICES_DIR = "/app/voices"
SHARED_DIR = "/app/shared"

# --- Setup Celery App ---
celery_app = Celery("tts_worker", broker=REDIS_URL, backend=REDIS_URL)

# --- Bot Setup ---
intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.members = True

bot = commands.Bot(command_prefix=PREFIX, intents=intents)

# --- State ---
guild_queues = {}  # GuildID -> asyncio.Queue (stores TTSRequest references)
processing_tasks = {}  # GuildID -> Task (the background loop)
currently_playing = {}  # GuildID -> TTSRequest (the one currently being voiced)


# --- Helper: Check Available Voices ---
def get_available_voices():
    voices = []
    if os.path.exists(VOICES_DIR):
        for filename in os.listdir(VOICES_DIR):
            name, ext = os.path.splitext(filename)
            if ext in [".safetensors", ".wav"]:
                voices.append(name.lower())
    return voices


# --- Queue Logic ---


class TTSRequest:
    """Tracks a Celery task and its associated Discord context."""

    def __init__(self, task, user_name, text, filepath):
        self.task = task
        self.user_name = user_name
        self.text = text
        self.filepath = filepath


async def process_queue(guild_id):
    """Background loop that waits for Celery tasks to finish and plays them sequentially."""
    while True:
        request = await guild_queues[guild_id].get()
        currently_playing[guild_id] = request

        guild = bot.get_guild(guild_id)
        vc = guild.voice_client if guild else None

        if not vc:
            currently_playing[guild_id] = None
            guild_queues[guild_id].task_done()
            continue

        try:
            # 1. Wait for Celery worker to finish this specific task
            while not request.task.ready():
                await asyncio.sleep(0.1)

            if request.task.state == "FAILURE":
                print(f"Celery Task failed: {request.task.result}")
                currently_playing[guild_id] = None
                guild_queues[guild_id].task_done()
                continue

            # 2. Wait for the voice client to finish playing the previous audio
            while vc.is_playing():
                await asyncio.sleep(0.1)

            # 3. Play the Audio
            if os.path.exists(request.filepath):
                source = discord.FFmpegPCMAudio(request.filepath)
                play_done = asyncio.Event()

                def after_playing(error):
                    if os.path.exists(request.filepath):
                        try:
                            os.remove(request.filepath)
                        except:
                            pass
                    bot.loop.call_soon_threadsafe(play_done.set)
                    if error:
                        print(f"Player error: {error}")

                vc.play(source, after=after_playing)
                await play_done.wait()

        except Exception as e:
            print(f"Error during playback: {e}")

        currently_playing[guild_id] = None
        guild_queues[guild_id].task_done()


async def add_to_tts_queue(guild_id, user_name, text, voice_name):
    """Dispatches directly to Celery's queue and tracks the task locally."""
    if guild_id not in guild_queues:
        guild_queues[guild_id] = asyncio.Queue()
        processing_tasks[guild_id] = asyncio.create_task(process_queue(guild_id))

    task_id = str(uuid.uuid4())
    filename = f"{task_id}.wav"
    filepath = os.path.join(SHARED_DIR, filename)

    # Dispatch to Celery IMMEDIATELY. This puts the generation work into Celery's queue.
    task = celery_app.send_task(
        "worker.tasks.generate_tts_task",
        args=[text, voice_name, filename],
    )

    # Track the request so the bot knows what order to play them in
    request = TTSRequest(task, user_name, text, filepath)
    await guild_queues[guild_id].put(request)


async def listen_for_web_requests():
    """Background task to receive TTS requests from the Web UI."""
    r = aioredis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe("web_tts_requests")

    while True:
        try:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                data = json.loads(message["data"])
                guild_id = data["guild_id"]

                # Find the guild and check if bot is in a voice channel there
                guild = bot.get_guild(guild_id)
                if not guild:
                    print(f"❌ Web request ignored: Guild {guild_id} not found.")
                    continue

                vc = guild.voice_client
                if not vc:
                    print(
                        f"❌ Web request ignored: Not in a voice channel in {guild.name}."
                    )
                    continue

                # Add to queue
                task_id = data["task_id"]
                filename = f"web_{task_id}.wav"
                filepath = os.path.join(SHARED_DIR, filename)

                request = TTSRequest(
                    task=celery_app.AsyncResult(task_id),
                    user_name=data["user_name"],
                    text=data["text"],
                    filepath=filepath,
                )

                if guild_id not in guild_queues:
                    guild_queues[guild_id] = asyncio.Queue()
                    processing_tasks[guild_id] = asyncio.create_task(
                        process_queue(guild_id)
                    )

                await guild_queues[guild_id].put(request)

            await asyncio.sleep(0.5)  # Prevent CPU spinning
        except Exception as e:
            print(f"Web Listener Error: {e}")
            await asyncio.sleep(5)


# --- Events ---


@bot.event
async def on_ready():
    if not bot.user:
        print("Error: Bot user not found.")
        return
    database.init_db()  # Initialize SQLite
    print(f"Logged in as {bot.user.name}")
    bot.loop.create_task(listen_for_web_requests())


@bot.event
async def on_message(message):
    if message.author.bot or message.content.startswith(PREFIX):
        await bot.process_commands(message)
        return

    # Auto-TTS logic using SQLite
    bound_channel_id = database.get_bound_channel(message.guild.id)
    if bound_channel_id and message.channel.id == bound_channel_id:
        if message.author.voice and message.author.voice.channel:
            vc = message.guild.voice_client
            if vc and vc.channel == message.author.voice.channel:
                if message.author.voice.self_mute or message.author.voice.mute:
                    # Fetch persistent user settings
                    settings = database.get_user_settings(message.author.id)

                    if settings["use_prefix"]:
                        text_to_say = (
                            f"{message.author.display_name} says: {message.content}"
                        )
                    else:
                        text_to_say = message.content

                    await add_to_tts_queue(
                        message.guild.id,
                        message.author.display_name,
                        text_to_say,
                        settings["voice"],
                    )


# --- Commands ---


@bot.command()
async def join(ctx):
    """Joins your voice channel and binds to the text channel."""
    if not ctx.author.voice:
        return await ctx.send("You are not in a voice channel.")

    channel = ctx.author.voice.channel
    if ctx.voice_client:
        await ctx.voice_client.move_to(channel)
    else:
        await channel.connect()

    database.set_bound_channel(ctx.guild.id, ctx.channel.id)
    await ctx.send(f"Joined **{channel.name}** and bound to this text channel.")


@bot.command()
async def voice(ctx, name: str):
    """Sets your personal TTS voice."""
    available = get_available_voices()
    name = name.lower()
    if name not in available:
        return await ctx.send(f"❌ Voice `{name}` not found.")

    database.set_user_voice(ctx.author.id, name)
    await ctx.send(f"✅ Your voice is now **{name}**")


@bot.command()
async def prefix(ctx, setting: str):
    """Toggle the 'User says:' prefix (on/off)."""
    setting = setting.lower()
    if setting in ["on", "yes", "true"]:
        database.set_user_prefix(ctx.author.id, True)
        await ctx.send("✅ Prefix enabled: I will say your name before the message.")
    elif setting in ["off", "no", "false"]:
        database.set_user_prefix(ctx.author.id, False)
        await ctx.send("✅ Prefix disabled: I will only say the message content.")
    else:
        await ctx.send("Usage: `!prefix on` or `!prefix off`")


@bot.command()
async def queue(ctx):
    """Displays the items currently waiting in the queue (Plaintext)."""
    guild_id = ctx.guild.id

    # Get current and queued items
    current = currently_playing.get(guild_id)

    # Access internal queue list safely
    if guild_id in guild_queues:
        queue_list = list(guild_queues[guild_id]._queue)
    else:
        queue_list = []

    if not current and not queue_list:
        return await ctx.send("The queue is currently empty.")

    lines = ["**TTS Queue**"]

    # Currently Playing section
    if current:
        status = "🔊 Playing" if current.task.ready() else "⚙️ Generating"
        # Truncate text to 50 chars to prevent hitting message limits
        text_preview = (
            current.text[:50] + "..." if len(current.text) > 50 else current.text
        )
        lines.append(f"__Now:__ **{current.user_name}** ({status}): {text_preview}")

    # Up Next section
    if queue_list:
        lines.append("\n__Up Next:__")
        for i, req in enumerate(queue_list[:10], 1):  # Show max 10 items
            status = "Ready" if req.task.ready() else "Queued"
            text_preview = req.text[:50] + "..." if len(req.text) > 50 else req.text
            lines.append(f"{i}. **{req.user_name}** [{status}]: {text_preview}")

        if len(queue_list) > 10:
            lines.append(f"...and {len(queue_list) - 10} more.")
    else:
        if current:
            lines.append("\n(No other items pending)")

    # Send as a standard message
    await ctx.send("\n".join(lines))


@bot.command()
async def s(ctx, *, text: str):
    """Speaks the text directly (no 'User says:' prefix) using your saved voice."""
    if not ctx.voice_client:
        return await ctx.send("Use `!join` first.")

    # Fetch persistent voice setting from DB
    settings = database.get_user_settings(ctx.author.id)
    voice_name = settings["voice"]

    # We skip the prefix logic here because !s is intended for direct speech
    await add_to_tts_queue(ctx.guild.id, ctx.author.display_name, text, voice_name)


@bot.command()
async def multi(ctx, *, text: str):
    """Speaks multiple lines. Supports 'voice: text' per line."""
    if not ctx.voice_client:
        return await ctx.send("Use `!join` first.")

    # Pre-fetch data needed for the loop
    available_voices = get_available_voices()
    settings = database.get_user_settings(ctx.author.id)
    default_voice = settings["voice"]

    lines = text.splitlines()
    for line in lines:
        line = line.strip()
        if not line:
            continue

        voice_to_use = default_voice
        text_to_say = line

        # Check if the line specifies a custom voice (e.g., "bella: hello there")
        if ":" in line:
            potential_voice, actual_text = line.split(":", 1)
            potential_voice = potential_voice.strip().lower()

            if potential_voice in available_voices:
                voice_to_use = potential_voice
                text_to_say = actual_text.strip()

        # Add each line to the queue
        await add_to_tts_queue(
            ctx.guild.id, ctx.author.display_name, text_to_say, voice_to_use
        )


@bot.command()
async def stop(ctx):
    if ctx.voice_client:
        ctx.voice_client.stop()

        # Clear the local queue AND cancel the pending tasks in Celery!
        if ctx.guild.id in guild_queues:
            while not guild_queues[ctx.guild.id].empty():
                try:
                    req = guild_queues[ctx.guild.id].get_nowait()
                    # Tell Celery to kill the task if it hasn't started or is running
                    celery_app.control.revoke(req.task.id, terminate=True)
                    guild_queues[ctx.guild.id].task_done()
                except asyncio.QueueEmpty:
                    break

    await ctx.send("Stopped playback and cancelled pending tasks.")


@bot.command()
async def voices(ctx):
    available = get_available_voices()
    if not available:
        return await ctx.send("No voices available.")
    await ctx.send(f"**Available Voices:** \n```\n{'\n'.join(available)}\n```")


if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN not set in environment variables.")
    else:
        bot.run(TOKEN)
