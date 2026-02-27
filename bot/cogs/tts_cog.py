"""TTS Cog - Commands for text-to-speech functionality."""

from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from discord.ext import commands

from ..utils.config import (
    MAX_QUEUE_DISPLAY,
    TEXT_PREVIEW_LENGTH,
    celery_app,
    get_available_voices,
)
from ..utils.db import get_user_voice
from ..utils.queue import (
    TTSRequest,
    add_to_tts_queue,
    currently_playing,
    guild_queues,
)

if TYPE_CHECKING:
    from discord.ext.commands import Context


class TTSCog(commands.Cog):
    """Cog for TTS-related commands."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @commands.command()
    async def queue(self, ctx: Context[commands.Bot]) -> None:
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

        if current:
            status: str = "Playing" if current.task.ready() else "Generating"
            # Truncate text to TEXT_PREVIEW_LENGTH chars to prevent hitting message limits
            text_preview: str = (
                current.text[:TEXT_PREVIEW_LENGTH] + "..." if len(current.text) > TEXT_PREVIEW_LENGTH else current.text
            )
            lines.append(f"__Now:__ **{current.user_name}** ({status}): {text_preview}")

        if queue_list:
            lines.append("\n__Up Next:__")
            for i, req in enumerate(queue_list[:MAX_QUEUE_DISPLAY], 1):
                status = "Ready" if req.task.ready() else "Queued"
                text_preview = (
                    req.text[:TEXT_PREVIEW_LENGTH] + "..." if len(req.text) > TEXT_PREVIEW_LENGTH else req.text
                )
                lines.append(f"{i}. **{req.user_name}** [{status}]: {text_preview}")

            if len(queue_list) > MAX_QUEUE_DISPLAY:
                lines.append(f"...and {len(queue_list) - MAX_QUEUE_DISPLAY} more.")
        elif current:
            lines.append("\n(No other items pending)")

        # Send as a standard message
        await ctx.send("\n".join(lines))

    @commands.command()
    async def s(self, ctx: Context[commands.Bot], *, text: str) -> None:
        """Say text without username prefix."""
        if not ctx.voice_client:
            await ctx.send("Use `!join` first.")
            return

        if not ctx.guild:
            await ctx.send("This command must be used in a server.")
            return

        voice_name: str = await get_user_voice(ctx.author.id) or "alba"
        await add_to_tts_queue(ctx.guild.id, ctx.author.display_name, text, voice_name)

    @commands.command()
    async def multi(self, ctx: Context[commands.Bot], *, text: str) -> None:
        """Say multiple lines with optional voice prefixes."""
        if not ctx.voice_client:
            await ctx.send("Use `!join` first.")
            return

        if not ctx.guild:
            await ctx.send("This command must be used in a server.")
            return

        # Get user's default voice once for efficiency
        default_voice: str = await get_user_voice(ctx.author.id) or "alba"

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
            voice_name = default_voice
            text_to_say = line.strip()
            await add_to_tts_queue(ctx.guild.id, ctx.author.display_name, text_to_say, voice_name)

    @commands.command()
    async def stop(self, ctx: Context[commands.Bot]) -> None:
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


async def setup(bot: commands.Bot) -> None:
    """Load the TTS cog."""
    await bot.add_cog(TTSCog(bot))
