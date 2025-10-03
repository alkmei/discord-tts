import discord
from discord.ext import commands
import asyncio
import json
import os
from typing import Dict, Optional, List
import logging
import tempfile
from dotenv import load_dotenv

from queue import Queue

load_dotenv()

# Set up logging
logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)

# Bot configuration
intents: discord.Intents = discord.Intents.default()
intents.message_content = True
intents.voice_states = True
intents.guilds = True
intents.members = True

bot: commands.Bot = commands.Bot(command_prefix="!", intents=intents)


class TTSBot:
    def __init__(self) -> None:
        self.voice_clients: Dict[int, discord.VoiceClient] = {}
        self.monitored_channels: Dict[int, int] = {}  # guild_id: text_channel_id
        self.user_voices: Dict[int, str] = {}  # user_id: voice_name
        self.audio_queues: Dict[int, Queue[str]] = {}  # guild_id: Queue of audio files
        self.audio_players: Dict[int, bool] = {}  # guild_id: is_playing
        self.load_user_voices()

    def load_user_voices(self) -> None:
        """Load user voice preferences from file"""
        try:
            if os.path.exists("user_voices.json"):
                with open("user_voices.json", "r") as f:
                    # Convert string keys back to int
                    data: Dict[str, str] = json.load(f)
                    self.user_voices = {int(k): v for k, v in data.items()}
        except Exception as e:
            logger.error(f"Error loading user voices: {e}")

    def save_user_voices(self) -> None:
        """Save user voice preferences to file"""
        try:
            # Convert int keys to string for JSON serialization
            data: Dict[str, str] = {str(k): v for k, v in self.user_voices.items()}
            with open("user_voices.json", "w") as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Error saving user voices: {e}")

    def get_user_voice(self, user_id: int) -> str:
        """Get voice for a user, assign default if none exists"""
        if user_id not in self.user_voices:
            # Assign a default voice (you can customize this logic)
            voices: List[str] = [
                "en-US-AriaNeural",
                "en-US-JennyNeural",
                "en-US-GuyNeural",
                "en-US-AndrewNeural",
                "en-US-EmmaNeural",
                "en-US-BrianNeural",
            ]
            self.user_voices[user_id] = voices[user_id % len(voices)]
            self.save_user_voices()
        return self.user_voices[user_id]

    async def speak_text(
        self, voice_client: discord.VoiceClient, text: str, voice: str, guild_id: int
    ) -> None:
        """Convert text to speech and add to queue for simultaneous playback"""
        try:
            # This uses edge-tts (install with: pip install edge-tts)
            import edge_tts

            # Create temporary file for audio
            with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as tmp_file:
                tmp_path: str = tmp_file.name

            # Generate speech
            communicate: edge_tts.Communicate = edge_tts.Communicate(text, voice)
            await communicate.save(tmp_path)

            # Add to simultaneous playback
            if guild_id not in self.audio_queues:
                self.audio_queues[guild_id] = Queue()

            self.audio_queues[guild_id].put(tmp_path)

            # Start audio player if not already running
            if not self.audio_players.get(guild_id, False):
                await self.start_audio_player(voice_client, guild_id)

        except Exception as e:
            logger.error(f"Error in TTS: {e}")

    async def start_audio_player(
        self, voice_client: discord.VoiceClient, guild_id: int
    ) -> None:
        """Start the audio player for sequential playback (no mixing)"""
        if self.audio_players.get(guild_id, False):
            return  # Already running

        self.audio_players[guild_id] = True

        try:
            while (
                not self.audio_queues[guild_id].empty() or voice_client.is_connected()
            ):
                if self.audio_queues[guild_id].empty():
                    await asyncio.sleep(0.1)
                    continue

                # Get the next audio file
                audio_file: str = self.audio_queues[guild_id].get()

                if not audio_file:
                    await asyncio.sleep(0.1)
                    continue

                # Play the audio file
                if voice_client.is_connected() and not voice_client.is_playing():
                    audio_source: discord.FFmpegPCMAudio = discord.FFmpegPCMAudio(
                        audio_file
                    )
                    voice_client.play(audio_source)

                    while voice_client.is_playing():
                        await asyncio.sleep(0.1)

                # Clean up the audio file
                try:
                    os.unlink(audio_file)
                except:
                    pass

                await asyncio.sleep(0.1)

        except Exception as e:
            logger.error(f"Error in audio player: {e}")
        finally:
            self.audio_players[guild_id] = False


# Initialize TTS bot
tts_bot: TTSBot = TTSBot()


async def check_muted_user_tts(message: discord.Message) -> None:
    """
    Check if the message author is muted and auto-convert their message to TTS.

    This function:
    - Checks if the bot is in a voice channel for the guild
    - Verifies the message is from the monitored text channel
    - Confirms the author is in the same voice channel as the bot
    - Detects if the author is muted (self-muted or server-muted)
    - Automatically converts their message to TTS if muted

    Args:
        message: The Discord message to check
    """
    # Ensure this is a guild message
    if not message.guild:
        return

    guild_id: int = message.guild.id

    # Check if bot is in a voice channel for this guild
    if guild_id not in tts_bot.voice_clients:
        return

    # Check if this is the monitored text channel
    if guild_id not in tts_bot.monitored_channels:
        return

    if message.channel.id != tts_bot.monitored_channels[guild_id]:
        return

    # Check if the author is a member (not a webhook or system message)
    if not isinstance(message.author, discord.Member):
        return

    # Check if the author is in a voice channel
    if not message.author.voice:
        return

    # Get the voice client for this guild
    voice_client: Optional[discord.VoiceClient] = tts_bot.voice_clients.get(guild_id)
    if not voice_client or not voice_client.is_connected():
        return

    # Check if they're in the same voice channel as the bot
    if message.author.voice.channel != voice_client.channel:
        return

    # Check if the user is muted (either self-muted or server-muted)
    is_self_muted: bool = message.author.voice.self_mute
    is_server_muted: bool = message.author.voice.mute

    if is_self_muted or is_server_muted:
        # Don't process commands as TTS (commands start with !)
        if message.content.startswith("!"):
            return

        # Don't process empty messages
        if not message.content.strip():
            return

        # Get the user's voice preference and convert their message to TTS
        user_voice: str = tts_bot.get_user_voice(message.author.id)

        # Format the speech text with the user's display name
        speech_text: str = f"{message.author.display_name} says: {message.content}"

        # Queue the TTS audio for playback
        await tts_bot.speak_text(voice_client, speech_text, user_voice, guild_id)


@bot.event
async def on_ready() -> None:
    print(f"{bot.user} has connected to Discord!")


@bot.event
async def on_message(message: discord.Message) -> None:
    # Don't respond to bot messages
    if message.author.bot:
        return

    # Check if this message should be auto-converted to TTS for muted users
    if message.guild:
        await check_muted_user_tts(message)

    # Process other commands
    await bot.process_commands(message)


@bot.command(name="join")
async def join_voice_channel(ctx: commands.Context[commands.Bot]) -> None:
    """Join the voice channel of the user who sent the command"""
    if not isinstance(ctx.author, discord.Member):
        return
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return
    if ctx.author.voice is None:
        await ctx.send("You need to be in a voice channel for me to join!")
        return

    if not isinstance(ctx.author.voice.channel, discord.VoiceChannel):
        await ctx.send("You need to be in a voice channel for me to join!")
        return
    voice_channel: discord.VoiceChannel = ctx.author.voice.channel
    guild_id: int = ctx.guild.id

    try:
        # Join the voice channel
        voice_client: discord.VoiceClient = await voice_channel.connect()
        tts_bot.voice_clients[guild_id] = voice_client

        # Set this text channel as the monitored channel
        tts_bot.monitored_channels[guild_id] = ctx.channel.id

        # Initialize audio queue and player for this guild
        if guild_id not in tts_bot.audio_queues:
            tts_bot.audio_queues[guild_id] = Queue()
        tts_bot.audio_players[guild_id] = False

        await ctx.send(
            f"Joined {voice_channel.name}! Use `!s <message>` to convert text to speech. Multiple voices can speak simultaneously!"
        )

    except discord.errors.ClientException as e:
        await ctx.send(f"Error: {e}")
    except Exception as e:
        await ctx.send(f"Error joining voice channel: {str(e)}")


@bot.command(name="leave")
async def leave_voice_channel(ctx: commands.Context[commands.Bot]) -> None:
    """Leave the current voice channel"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return
    guild_id: int = ctx.guild.id

    if guild_id in tts_bot.voice_clients:
        voice_client: discord.VoiceClient = tts_bot.voice_clients[guild_id]
        await voice_client.disconnect()
        del tts_bot.voice_clients[guild_id]

        # Remove monitored channel
        if guild_id in tts_bot.monitored_channels:
            del tts_bot.monitored_channels[guild_id]

        # Clean up audio queue and player
        if guild_id in tts_bot.audio_queues:
            # Clear any remaining audio files
            while not tts_bot.audio_queues[guild_id].empty():
                try:
                    audio_file: str = tts_bot.audio_queues[guild_id].get()
                    os.unlink(audio_file)
                except:
                    pass
            del tts_bot.audio_queues[guild_id]

        if guild_id in tts_bot.audio_players:
            tts_bot.audio_players[guild_id] = False
            del tts_bot.audio_players[guild_id]

        await ctx.send("Left the voice channel!")
    else:
        await ctx.send("I'm not in a voice channel!")


@bot.command(name="voice")
async def set_voice(
    ctx: commands.Context[commands.Bot], voice_name: Optional[str] = None
) -> None:
    """Set or view your TTS voice"""
    if voice_name is None:
        current_voice: str = tts_bot.get_user_voice(ctx.author.id)
        await ctx.send(f"Your current voice is: {current_voice}")
        return

    # List of available voices (customize as needed)
    available_voices: List[str] = [
        "en-US-AriaNeural",
        "en-US-JennyNeural",
        "en-US-GuyNeural",
        "en-US-AndrewNeural",
        "en-US-EmmaNeural",
        "en-US-BrianNeural",
        "en-GB-SoniaNeural",
        "en-GB-RyanNeural",
        "en-AU-NatashaNeural",
    ]

    if voice_name in available_voices:
        tts_bot.user_voices[ctx.author.id] = voice_name
        tts_bot.save_user_voices()
        await ctx.send(f"Your voice has been set to: {voice_name}")
    else:
        voices_list: str = "\n".join(available_voices)
        await ctx.send(f"Invalid voice. Available voices:\n```{voices_list}```")


@bot.command(name="voices")
async def list_voices(ctx: commands.Context[commands.Bot]) -> None:
    """List all available TTS voices"""
    available_voices: List[str] = [
        "en-US-AriaNeural",
        "en-US-JennyNeural",
        "en-US-GuyNeural",
        "en-US-AndrewNeural",
        "en-US-EmmaNeural",
        "en-US-BrianNeural",
        "en-GB-SoniaNeural",
        "en-GB-RyanNeural",
        "en-AU-NatashaNeural",
    ]
    voices_list: str = "\n".join(available_voices)
    await ctx.send(f"Available voices:\n```{voices_list}```")


@bot.command(name="s")
async def speak_text_command(ctx: commands.Context[commands.Bot], *, text: str) -> None:
    """Convert text to speech using !s command"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return
    guild_id: int = ctx.guild.id
    voice_client: Optional[discord.VoiceClient] = tts_bot.voice_clients.get(guild_id)

    if not voice_client or not voice_client.is_connected():
        await ctx.send("I need to be in a voice channel first! Use `!join`")
        return

    # Check if this is a monitored channel
    if (
        guild_id not in tts_bot.monitored_channels
        or ctx.channel.id != tts_bot.monitored_channels[guild_id]
    ):
        await ctx.send("I'm only providing TTS in the channel where I was summoned!")
        return

    user_voice: str = tts_bot.get_user_voice(ctx.author.id)

    speech_text: str = f"{ctx.author.display_name} says: {text} "
    await tts_bot.speak_text(voice_client, speech_text, user_voice, guild_id)


@bot.command(name="help_tts")
async def help_command(ctx: commands.Context[commands.Bot]) -> None:
    """Show available TTS commands"""
    help_text: str = """
**TTS Bot Commands:**
`!join` - Join your current voice channel
`!leave` - Leave the voice channel
`!s <message>` - Convert text to speech (multiple can overlap!)
`!voice [voice_name]` - Set or view your TTS voice
`!voices` - List all available voices
`!test [text]` - Test TTS functionality
`!help_tts` - Show this help message

**Features:**
- Multiple people can use `!s` simultaneously for overlapping speech
- Each user gets their own unique voice
    """
    await ctx.send(help_text)


@bot.command(name="test")
async def test_tts(
    ctx: commands.Context[commands.Bot], *, text: str = "This is a test message"
) -> None:
    """Test TTS functionality"""
    if not ctx.guild:
        await ctx.send("This command can only be used in a server.")
        return

    guild_id: int = ctx.guild.id
    voice_client: Optional[discord.VoiceClient] = tts_bot.voice_clients.get(guild_id)

    if not voice_client or not voice_client.is_connected():
        await ctx.send("I need to be in a voice channel first! Use `!join`")
        return

    user_voice: str = tts_bot.get_user_voice(ctx.author.id)
    await tts_bot.speak_text(voice_client, text, user_voice, guild_id)
    await ctx.send("TTS test completed!")


# Run the bot
if __name__ == "__main__":
    # Make sure to set your bot token as an environment variable
    TOKEN: str = os.environ.get("DISCORD_BOT_TOKEN", "")

    if not TOKEN:
        print("Please set the DISCORD_BOT_TOKEN environment variable")
        exit(1)

    bot.run(TOKEN)
