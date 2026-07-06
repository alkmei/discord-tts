import io
import logging
import tempfile
from pathlib import Path

from celery import shared_task
from django.core.files.base import ContentFile
from pocket_tts import export_model_state
from pydub import AudioSegment

from discord_tts.speech.tts_model import get_model

from .models import Voice

logger = logging.getLogger(__name__)

AUDIO_MAX_MS = 30000


@shared_task
def generate_safetensors(voice_id: int):
    voice = Voice.objects.get(id=voice_id)

    logger.info(
        "Starting safetensor regeneration for voice_id=%s, audio=%s",
        voice_id,
        voice.audio_source.path,
    )
    model = get_model()

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp_dir_path = Path(tmp_dir)

        try:
            audio = AudioSegment.from_file(voice.audio_source.path)

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
                    f"{voice.name}.safetensors",
                    ContentFile(f.read()),
                    save=False,
                )
                Voice.objects.filter(pk=voice.pk).update(
                    processed_safetensor=voice.processed_safetensor.name,
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
def convert_to_ogg_opus(voice_id: int):
    try:
        voice = Voice.objects.get(id=voice_id)
        if not voice.audio_source or not voice.audio_source.name:
            return

        old_file_path = voice.audio_source.name

        input_data = io.BytesIO(voice.audio_source.read())
        audio = AudioSegment.from_file(input_data)

        if len(audio) > AUDIO_MAX_MS:
            audio = audio[:AUDIO_MAX_MS]

        output_buffer = io.BytesIO()
        audio.export(
            output_buffer,
            format="ogg",
            codec="libopus",
            parameters=["-ar", "48000", "-b:a", "32k"],
        )

        new_filename = f"{Path(voice.audio_source.name).stem}.ogg"
        voice.audio_source.save(
            new_filename,
            ContentFile(output_buffer.getvalue()),
            save=False,
        )
        Voice.objects.filter(pk=voice.pk).update(audio_source=voice.audio_source.name)

        if old_file_path != voice.audio_source.name:
            voice.audio_source.storage.delete(old_file_path)
            logger.info("Deleted old file: %s", old_file_path)
        generate_safetensors.delay(voice.pk)

        logger.info("Successfully converted Voice %s to Ogg Opus", voice_id)

    except Exception:
        logger.exception("Failed to convert Voice %s", voice_id)
