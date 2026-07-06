import io
import logging
import tempfile
from pathlib import Path

from celery import shared_task
from celery.utils.log import get_task_logger
from django.core.files.base import ContentFile
from pocket_tts import export_model_state
from pydub import AudioSegment

from discord_tts.speech.tts_model import get_model

from .models import Voice

logger = logging.getLogger(__name__)

AUDIO_MAX_MS = 30000


logger = get_task_logger(__name__)


@shared_task
def generate_safetensors(voice_id: int):
    try:
        voice = Voice.objects.get(id=voice_id)
        if not voice.audio_source:
            logger.warning("Voice %s has no audio source", voice_id)
            return

        # Capture old path for cleanup
        old_safetensor_path = (
            voice.processed_safetensor.name if voice.processed_safetensor else None
        )
        model = get_model()
        new_filename = f"{voice.name}.safetensors"

        with (
            tempfile.TemporaryDirectory() as tmp_dir,
            voice.audio_source.open("rb") as f_in,
        ):
            tmp_dir_path = Path(tmp_dir)
            temp_input_path = tmp_dir_path / "input_source.ogg"
            safetensor_temp_path = tmp_dir_path / "output.safetensors"

            # Download in case of cloud
            with temp_input_path.open("wb") as f_out:
                for chunk in f_in.chunks():
                    f_out.write(chunk)

            model_state = model.get_state_for_audio_prompt(str(temp_input_path))
            export_model_state(model_state, str(safetensor_temp_path))

            with safetensor_temp_path.open("rb") as f_st:
                voice.processed_safetensor.save(
                    new_filename,
                    ContentFile(f_st.read()),
                    save=False,
                )

        Voice.objects.filter(pk=voice.pk).update(
            processed_safetensor=voice.processed_safetensor.name,
        )

        if (
            old_safetensor_path
            and old_safetensor_path != voice.processed_safetensor.name
        ):
            voice.processed_safetensor.storage.delete(old_safetensor_path)
            logger.info("Deleted old safetensor: %s", old_safetensor_path)

        logger.info("Successfully generated safetensors for Voice %s", voice_id)

    except Exception:
        logger.exception("Error generating safetensors for voice %s", voice_id)
        raise


@shared_task
def convert_to_ogg_opus(voice_id: int):
    try:
        voice = Voice.objects.get(id=voice_id)
        if not voice.audio_source or not voice.audio_source.name:
            return

        old_file_full_path = voice.audio_source.name

        base_filename = Path(voice.audio_source.name).stem
        new_filename = f"{base_filename}.ogg"

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

        voice.audio_source.save(
            new_filename,
            ContentFile(output_buffer.getvalue()),
            save=False,
        )

        Voice.objects.filter(pk=voice.pk).update(audio_source=voice.audio_source.name)

        if old_file_full_path != voice.audio_source.name:
            voice.audio_source.storage.delete(old_file_full_path)
            logger.info("Deleted old file %s", old_file_full_path)

        generate_safetensors.delay(voice.pk)
        logger.info("Successfully converted Voice %s to Ogg Opus", voice_id)

    except Exception:
        logger.exception("Failed to convert Voice %s", voice_id)
