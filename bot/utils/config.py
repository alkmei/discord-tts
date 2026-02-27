"""Configuration and constants for the Discord TTS Bot."""

from __future__ import annotations

import logging
import os
from pathlib import Path

from celery import Celery
from dotenv import load_dotenv

load_dotenv()

# --- Configuration ---
TOKEN: str = os.getenv("DISCORD_BOT_TOKEN", "")
RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "")
PREFIX: str = "!"
VOICES_DIR: Path = Path("/app/voices")
SHARED_DIR: Path = Path("/app/shared")
DB_PATH: Path = Path("/app/data/state.sqlite")

# Constants for queue display
TEXT_PREVIEW_LENGTH: int = 50
MAX_QUEUE_DISPLAY: int = 10

# Celery setup
celery_app: Celery = Celery("tts_worker", broker=RABBITMQ_URL, backend="rpc://")

# Configure logging
logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


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
