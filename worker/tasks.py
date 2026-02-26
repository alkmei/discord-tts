"""Celery worker tasks for TTS generation."""

from __future__ import annotations

import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import scipy.io.wavfile
from celery import Celery
from pocket_tts import TTSModel  # type: ignore[import]

if TYPE_CHECKING:
    import torch

# Configure logging
logging.basicConfig(level=logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)

# Initialize Celery
app: Celery = Celery("tts_worker", broker=os.getenv("RABBITMQ_URL"), backend="rpc://")

# Constants
VOICES_DIR: Path = Path("/app/voices")
SHARED_DIR: Path = Path("/app/shared")
LRU_CACHE_SIZE: int = 4


# Global model variable (loaded once when worker starts)
# Using a class to avoid global statement issues
class ModelState:
    """Container for the TTS model singleton."""

    model: TTSModel | None = None


def get_model() -> TTSModel:
    """Singleton to load the base model only once."""
    if ModelState.model is None:
        logger.info("Worker: Loading Base Pocket TTS Model...")
        ModelState.model = TTSModel.load_model()
        logger.info("Worker: Model loaded on %s", ModelState.model.device)
    return ModelState.model


@lru_cache(maxsize=LRU_CACHE_SIZE)
def get_cached_voice_state(voice_name: str) -> torch.Tensor:
    """
    Loads voice state from disk.
    Keeps only the last 4 used voices in memory.
    """
    model: TTSModel = get_model()

    # Try safetensors first, then wav
    safe_path: Path = VOICES_DIR / f"{voice_name}.safetensors"
    wav_path: Path = VOICES_DIR / f"{voice_name}.wav"

    target_path: Path | None = None
    if safe_path.exists():
        target_path = safe_path
    elif wav_path.exists():
        target_path = wav_path

    if target_path:
        logger.info("Worker: Loading voice '%s' into LRU Cache.", voice_name)
        return model.get_state_for_audio_prompt(str(target_path))  # type: ignore[return-value]

    # Fallback to a default if file not found (or raise error)
    logger.warning("Worker: Voice %s not found, using internal default.", voice_name)
    return model.get_state_for_audio_prompt("alba")  # type: ignore[return-value] # internal default


@app.task
def generate_tts_task(text: str, voice_name: str, output_filename: str) -> str:
    """Celery Task: Generates audio and saves to shared volume."""
    model: TTSModel = get_model()

    # Get voice from LRU cache
    voice_state: torch.Tensor = get_cached_voice_state(voice_name)

    # Generate Audio. The "." prefix improves prosody.
    audio_tensor: torch.Tensor = model.generate_audio(voice_state, "." + text)  # type: ignore[arg-type]

    # Save to shared volume
    output_path: Path = SHARED_DIR / output_filename
    scipy.io.wavfile.write(str(output_path), model.sample_rate, audio_tensor.cpu().numpy())

    return str(output_path)
