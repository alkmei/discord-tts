import os
from functools import lru_cache

import scipy.io.wavfile
from celery import shared_task
from django.conf import settings

from .tts_model import get_model


@lru_cache(maxsize=4)
def get_cached_voice_state(voice_name):
    """Loads voice state from disk.

    Keeps only the last 4 used voices in memory.
    """
    model = get_model()
    voices_dir = settings.TTS_SHARED_DIR

    # Try safetensors first, then wav
    safe_path = os.path.join(voices_dir, f"{voice_name}.safetensors")
    wav_path = os.path.join(voices_dir, f"{voice_name}.wav")

    target_path = None
    if os.path.exists(safe_path):
        target_path = safe_path
    elif os.path.exists(wav_path):
        target_path = wav_path

    if target_path:
        print(f"📂 Worker: Loading voice '{voice_name}' into LRU Cache.")
        return model.get_state_for_audio_prompt(target_path)

    # Fallback to a default if file not found (or raise error)
    print(f"⚠️ Worker: Voice {voice_name} not found, using internal default.")
    return model.get_state_for_audio_prompt("alba")  # internal default


@shared_task
def generate_tts_task(text, voice_name, output_filename):
    """
    Celery Task: Generates audio and saves to shared volume.
    """
    model = get_model()

    # Get voice from LRU cache
    voice_state = get_cached_voice_state(voice_name)

    # Generate Audio. The "." prefix improves prosidy.
    audio_tensor = model.generate_audio(voice_state, "." + text)

    # Save to shared volume
    output_path = os.path.join("/app/shared", output_filename)
    scipy.io.wavfile.write(output_path, model.sample_rate, audio_tensor.cpu().numpy())

    return output_path
