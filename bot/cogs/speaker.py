import asyncio

import discord
import redis
from discord.ext import commands


class SpeakerCog(commands.Cog):
    """Manage sending audio to Discord

    Listens for signals from TTS workers to see when the audio clip is ready
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.redis_url = "redis://localhost"
        # Stores a queue for every guild: {guild_id: asyncio.Queue}
        self.queues = {}
        # Tracks which guilds are currently playing audio
        self.playing_tasks = {}

    async def cog_load(self):
        """Start the Redis listener with the cog."""
        self.bot.loop.create_task(self.redis_listener())

    async def redis_listener(self):
        """Listen for signals from the worker."""
        r = redis.from_url(self.redis_url)
        pubsub = r.pubsub()
        await pubsub.subscribe("tts_play_queue")

        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await self.enqueue_audio(data)

    async def enqueue_audio(self, data):
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

    # TODO: The bot needs to have fair scheduling across multiple queues
    async def play_loop(self, guild_id):
        """Continuously plays audio from the queue until it's empty."""
        queue = self.queues[guild_id]

        while not queue.empty():
            data = await queue.get()
            channel_id = int(data["channel_id"])
            file_path = data["file_path"]

            await self.execute_play(guild_id, channel_id, file_path)

    async def execute_play(self, guild_id, channel_id, file_path):
        """Handles the actual Discord voice playback."""
        guild = self.bot.get_guild(guild_id)
        if not guild:
            return

        # Logic to find or connect to voice channel
        vc = guild.voice_client
        # Bot should already be in vc?
        # if not vc:
        #     channel = self.bot.get_channel(channel_id)
        #     vc = await channel.connect()

        # Play audio and wait for it to finish
        if vc and not vc.is_playing():
            # We use a Future to 'wait' until the audio is done playing
            done = asyncio.Event()

            def after_playing(error):
                if error:
                    print(f"Player error: {error}")
                # Signal that we are ready for the next file
                self.bot.loop.call_soon_threadsafe(done.set)

            vc.play(discord.FFmpegPCMAudio(file_path), after=after_playing)

            # Wait here until the 'after' callback triggers
            await done.wait()


async def setup(bot: commands.Bot):
    await bot.add_cog(SpeakerCog(bot))
