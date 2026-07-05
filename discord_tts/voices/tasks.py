import logging
import tempfile
from pathlib import Path

from celery import shared_task
from django.conf import settings
from django.core.files.base import ContentFile
from pocket_tts import export_model_state
from pydub import AudioSegment

from discord_tts.speech.tts_model import get_model

from .models import Voice

logger = logging.getLogger(__name__)

AUDIO_MAX_MS = 30000


@shared_task
def generate_safetensors(voice_id: int, audio_path: str):
    logger.info(
        "Starting safetensor regeneration for voice_id=%s, audio=%s",
        voice_id,
        audio_path,
    )

    voice = Voice.objects.get(id=voice_id)
    model = get_model()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        try:
            audio = AudioSegment.from_file(audio_path)

            temp_wav_path = tmp_dir_path / "inference_prompt.wav"
            audio.set_frame_rate(22050).set_channels(1).export(
                str(temp_wav_path),
                format="wav",
            )

            model_state_for_voice = model.get_state_for_audio_prompt(str(temp_wav_path))

            safetensor_temp_path = tmp_dir_path / f"{voice.name}_{voice_id}.safetensors"
            export_model_state(model_state_for_voice, str(safetensor_temp_path))

            with safetensor_temp_path.open("rb") as f:
                voice.processed_safetensor.save(
                    f"{voice.name}_processed.safetensors",
                    ContentFile(f.read()),
                    save=True,
                )

            logger.info(
                "Safetensor regeneration complete for voice '%s' (id=%s)",
                voice.name,
                voice_id,
            )

        except Exception:
            logger.exception(
                "Error generating safetensors for voice %s",
                voice_id,
            )
            raise


@shared_task
def convert_to_ogg_opus(voice_id):
    try:
        voice = Voice.objects.get(id=voice_id)
        if not voice.audio_source:
            return

        original_path = voice.audio_source.path
        ogg_path = f"{Path(original_path).stem}.ogg"

        audio = AudioSegment.from_file(original_path)

        # Clip to 30 seconds
        if len(audio) > AUDIO_MAX_MS:
            audio = audio[:AUDIO_MAX_MS]

        # Export to Ogg Opus
        # We specify 'libopus' codec for high quality/low bitrate
        audio.export(
            ogg_path,
            format="ogg",
            codec="libopus",
            parameters=["-ar", "48000", "-b:a", "32k"],  # Discord-optimized settings
        )

        # Update model
        # We update the 'name' attribute of the FileField to the new path
        # This keeps the file in the same directory but points to the .ogg
        relative_path = str(Path(ogg_path).relative_to(settings.MEDIA_ROOT))
        voice.audio_source.name = relative_path
        voice.save(update_fields=["audio_source"])

        # Cleanup original file if it was different
        if original_path != ogg_path and Path(original_path).exists():
            Path(original_path).unlink()

        generate_safetensors.delay(voice.pk, relative_path)

        logger.info("Successfully converted Voice %s to Ogg Opus", voice_id)

    except Exception:
        logger.exception("Failed to convert Voice %s", voice_id)
