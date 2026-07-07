import logging
import typing

from discord_tts.speech.dispatcher import dispatch_tts
from discord_tts.speech.utils import resolve_mentions_agnostic

if typing.TYPE_CHECKING:
    import discord
    from celery.result import AsyncResult


logger = logging.getLogger(__name__)


def resolve_mentions(text: str, guild: discord.Guild) -> str:
    member_map = {member.id: member.display_name for member in guild.members}
    return resolve_mentions_agnostic(text, member_map)


def start_tts_task(
    text: str,
    voice: int | None,
    guild_id: int,
    channel_id: int,
) -> AsyncResult:
    voice_pk = voice or 1
    return dispatch_tts(
        text=text,
        voice_pk=voice_pk,
        guild_id=guild_id,
        channel_id=channel_id,
    )
