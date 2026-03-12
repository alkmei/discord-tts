import json
import discord
from discord.ext import commands
from celery import Celery
import asyncio
import os
import uuid
import emoji
import re
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
guild_queues = {}
processing_tasks = {}
currently_playing = {}

# --- Text Processing Helper ---


def clean_tts_text(message):
    """
    Cleans Discord message content for TTS:
    1. Replaces URLs with "(insert link here)"
    2. Resolves User Mentions to Nicknames
    3. Resolves Custom Emojis to their names
    4. Resolves Unicode Emojis to spoken words
    """
    content = message.content

    # Replace Links with "(insert link here)"
    # Regex matches http/https followed by non-whitespace characters
    content = re.sub(r"https?://\S+", "(insert link here)", content)

    # Resolve Mentions <@ID> or <@!ID> to Nicknames
    def replace_mention(match):
        user_id = int(match.group(1))
        member = message.guild.get_member(user_id)
        if member:
            return member.display_name
        return "someone"

    content = re.sub(r"<@!?(\d+)>", replace_mention, content)

    # Resolve Custom Emojis <:name:id> or <a:name:id> to "name"
    content = re.sub(r"<a?:([^:]+):\d+>", r" \1 ", content)

    # Resolve Unicode Emojis (🤨 -> face_with_raised_eyebrow)
    # We replace underscores with spaces and remove colons for cleaner TTS
    content = emoji.demojize(content, delimiters=(" ", " "))
    content = content.replace("_", " ").replace(":", "")

    # Final cleanup of whitespace
    content = " ".join(content.split())

    return content


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
    def __init__(self, task, user_name, text, filepath):
        self.task = task
        self.user_name = user_name
        self.text = text
        self.filepath = filepath


async def process_queue(guild_id):
    """Background loop that plays generated audio files sequentially."""
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
            # Wait for Celery worker to finish generation
            while not request.task.ready():
                await asyncio.sleep(0.1)

            if request.task.state == "FAILURE":
                print(f"Celery Task failed: {request.task.result}")
                currently_playing[guild_id] = None
                guild_queues[guild_id].task_done()
                continue

            # Wait for the voice client to be free
            while vc.is_playing():
                await asyncio.sleep(0.1)

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
    """Dispatches generation task to Celery and adds to local playback queue."""
    if guild_id not in guild_queues:
        guild_queues[guild_id] = asyncio.Queue()
        processing_tasks[guild_id] = asyncio.create_task(process_queue(guild_id))

    task_id = str(uuid.uuid4())
    filename = f"{task_id}.wav"
    filepath = os.path.join(SHARED_DIR, filename)

    task = celery_app.send_task(
        "worker.tasks.generate_tts_task",
        args=[text, voice_name, filename],
    )

    request = TTSRequest(task, user_name, text, filepath)
    await guild_queues[guild_id].put(request)


# --- Background Task: Web Requests ---


async def listen_for_web_requests():
    """Listens to Redis for TTS requests coming from the Web UI."""
    r = aioredis.from_url(REDIS_URL)
    pubsub = r.pubsub()
    await pubsub.subscribe("web_tts_requests")

    while True:
        try:
            message = await pubsub.get_message(ignore_subscribe_messages=True)
            if message:
                data = json.loads(message["data"])
                guild_id = data["guild_id"]
                guild = bot.get_guild(guild_id)

                if guild and guild.voice_client:
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

            await asyncio.sleep(0.5)
        except Exception as e:
            print(f"Web Listener Error: {e}")
            await asyncio.sleep(5)


# --- Events ---


@bot.event
async def on_ready():
    database.init_db()
    print(f"Logged in as {bot.user.name}")
    bot.loop.create_task(listen_for_web_requests())


@bot.event
async def on_message(message):
    if message.author.bot or message.content.startswith(PREFIX):
        await bot.process_commands(message)
        return

    # Clean the text using our new logic
    cleaned_text = clean_tts_text(message)

    # If the message is completely empty or just whitespace after cleaning, skip
    if not cleaned_text:
        return

    # Auto-TTS Check
    bound_channel_id = database.get_bound_channel(message.guild.id)
    if bound_channel_id and message.channel.id == bound_channel_id:
        if message.author.voice and message.author.voice.channel:
            vc = message.guild.voice_client
            # Check if bot is in the same channel as user
            if vc and vc.channel == message.author.voice.channel:
                # Check if user is muted (the usual condition for needing TTS)
                if message.author.voice.self_mute or message.author.voice.mute:
                    settings = database.get_user_settings(message.author.id)

                    text_to_say = cleaned_text
                    if settings["use_prefix"]:
                        text_to_say = (
                            f"{message.author.display_name} says: {cleaned_text}"
                        )

                    await add_to_tts_queue(
                        message.guild.id,
                        message.author.display_name,
                        text_to_say,
                        settings["voice"],
                    )


# --- Commands ---


@bot.command()
async def join(ctx):
    """Joins your voice channel and binds TTS to this text channel."""
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
        return await ctx.send(
            f"❌ Voice `{name}` not found. Use `!voices` to see list."
        )

    database.set_user_voice(ctx.author.id, name)
    await ctx.send(f"✅ Your voice is now **{name}**")


@bot.command()
async def prefix(ctx, setting: str):
    """Toggle the 'User says:' prefix (on/off)."""
    setting = setting.lower()
    if setting in ["on", "yes", "true"]:
        database.set_user_prefix(ctx.author.id, True)
        await ctx.send("✅ Prefix enabled.")
    elif setting in ["off", "no", "false"]:
        database.set_user_prefix(ctx.author.id, False)
        await ctx.send("✅ Prefix disabled.")
    else:
        await ctx.send("Usage: `!prefix on` or `!prefix off`")


@bot.command()
async def queue(ctx):
    """Displays the items currently waiting in the TTS queue."""
    guild_id = ctx.guild.id
    current = currently_playing.get(guild_id)
    queue_list = list(guild_queues[guild_id]._queue) if guild_id in guild_queues else []

    if not current and not queue_list:
        return await ctx.send("The queue is empty.")

    lines = ["**TTS Queue**"]
    if current:
        status = "🔊 Playing" if current.task.ready() else "⚙️ Generating"
        lines.append(
            f"__Now:__ **{current.user_name}**: {current.text[:50]}... ({status})"
        )

    if queue_list:
        lines.append("\n__Up Next:__")
        for i, req in enumerate(queue_list[:10], 1):
            status = "Ready" if req.task.ready() else "Queued"
            lines.append(f"{i}. **{req.user_name}**: {req.text[:50]}... [{status}]")

    await ctx.send("\n".join(lines))


@bot.command()
async def s(ctx, *, text: str):
    """Manually speaks text (ignores prefix setting)."""
    if not ctx.voice_client:
        return await ctx.send("Use `!join` first.")

    settings = database.get_user_settings(ctx.author.id)

    # We clean manual text too for emojis/mentions, but links are kept as "(link)"
    # Creating a dummy message object for the cleaner
    class DummyMsg:
        def __init__(self, c, g):
            self.content = c
            self.guild = g

    cleaned = clean_tts_text(DummyMsg(text, ctx.guild))
    await add_to_tts_queue(
        ctx.guild.id, ctx.author.display_name, cleaned, settings["voice"]
    )


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
    """Stops playback and clears the local and Celery queue."""
    if ctx.voice_client:
        ctx.voice_client.stop()

        if ctx.guild.id in guild_queues:
            while not guild_queues[ctx.guild.id].empty():
                try:
                    req = guild_queues[ctx.guild.id].get_nowait()
                    celery_app.control.revoke(req.task.id, terminate=True)
                    guild_queues[ctx.guild.id].task_done()
                except asyncio.QueueEmpty:
                    break

    await ctx.send("Playback stopped and queue cleared.")


@bot.command()
async def voices(ctx):
    """Lists available voice names."""
    available = get_available_voices()
    if not available:
        return await ctx.send("No voices found in voices folder.")
    await ctx.send(f"**Available Voices:** \n```\n{', '.join(available)}\n```")


if __name__ == "__main__":
    if not TOKEN:
        print("Error: DISCORD_BOT_TOKEN not set.")
    else:
        bot.run(TOKEN)
