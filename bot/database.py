import os
import sqlite3

DB_PATH = os.getenv("DB_PATH", "/app/data/settings.db")


def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("PRAGMA journal_mode=WAL;")
        # Table for user-specific preferences
        conn.execute("""
            CREATE TABLE IF NOT EXISTS user_settings (
                user_id INTEGER PRIMARY KEY,
                voice_name TEXT DEFAULT 'alba',
                use_prefix INTEGER DEFAULT 1
            )
        """)
        # Table for guild-specific settings (like bound channels)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS guild_settings (
                guild_id INTEGER PRIMARY KEY,
                bound_channel_id INTEGER
            )
        """)
        conn.commit()


def get_user_settings(user_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT voice_name, use_prefix FROM user_settings WHERE user_id = ?",
            (user_id,),
        )
        row = cursor.fetchone()
        if row:
            return {"voice": row[0], "use_prefix": bool(row[1])}
        return {"voice": "alba", "use_prefix": True}


def set_user_voice(user_id, voice_name):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO user_settings (user_id, voice_name) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET voice_name = excluded.voice_name
        """,
            (user_id, voice_name),
        )


def set_user_prefix(user_id, use_prefix: bool):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO user_settings (user_id, use_prefix) VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET use_prefix = excluded.use_prefix
        """,
            (user_id, int(use_prefix)),
        )


def get_bound_channel(guild_id):
    with sqlite3.connect(DB_PATH) as conn:
        cursor = conn.execute(
            "SELECT bound_channel_id FROM guild_settings WHERE guild_id = ?",
            (guild_id,),
        )
        row = cursor.fetchone()
        return row[0] if row else None


def set_bound_channel(guild_id, channel_id):
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO guild_settings (guild_id, bound_channel_id) VALUES (?, ?)
            ON CONFLICT(guild_id) DO UPDATE SET bound_channel_id = excluded.bound_channel_id
        """,
            (guild_id, channel_id),
        )
