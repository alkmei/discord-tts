"""Database utilities for the Discord TTS Bot."""

from __future__ import annotations

import aiosqlite

from .config import DB_PATH


async def init_db() -> None:
    """Initialize the SQLite database and create tables if they don't exist."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_voice_selections (
                user_id INTEGER PRIMARY KEY,
                voice_name TEXT NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS bound_channels (
                guild_id INTEGER PRIMARY KEY,
                channel_id INTEGER NOT NULL
            )
            """
        )
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_prefix_settings (
                user_id INTEGER PRIMARY KEY,
                prefix_enabled INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        await db.commit()


async def get_user_voice(user_id: int) -> str | None:
    """Get the voice selection for a user from the database."""
    async with (
        aiosqlite.connect(DB_PATH) as db,
        db.execute(
            "SELECT voice_name FROM user_voice_selections WHERE user_id = ?",
            (user_id,),
        ) as cursor,
    ):
        row = await cursor.fetchone()
        return row[0] if row else None


async def set_user_voice(user_id: int, voice_name: str) -> None:
    """Set or update the voice selection for a user in the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_voice_selections (user_id, voice_name) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET voice_name = excluded.voice_name
            """,
            (user_id, voice_name),
        )
        await db.commit()


async def get_bound_channel(guild_id: int) -> int | None:
    """Get the bound channel for a guild from the database."""
    async with (
        aiosqlite.connect(DB_PATH) as db,
        db.execute(
            "SELECT channel_id FROM bound_channels WHERE guild_id = ?",
            (guild_id,),
        ) as cursor,
    ):
        row = await cursor.fetchone()
        return row[0] if row else None


async def set_bound_channel(guild_id: int, channel_id: int) -> None:
    """Set or update the bound channel for a guild in the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO bound_channels (guild_id, channel_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET channel_id = excluded.channel_id
            """,
            (guild_id, channel_id),
        )
        await db.commit()


async def get_user_prefix_enabled(user_id: int) -> bool:
    """Get whether speech prefix is enabled for a user. Returns True if not set."""
    async with (
        aiosqlite.connect(DB_PATH) as db,
        db.execute(
            "SELECT prefix_enabled FROM user_prefix_settings WHERE user_id = ?",
            (user_id,),
        ) as cursor,
    ):
        row = await cursor.fetchone()
        # Default to True (enabled) if not set
        return bool(row[0]) if row else True


async def set_user_prefix_enabled(user_id: int, enabled: bool) -> None:
    """Set or update the speech prefix setting for a user in the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO user_prefix_settings (user_id, prefix_enabled) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET prefix_enabled = excluded.prefix_enabled
            """,
            (user_id, int(enabled)),
        )
        await db.commit()
