from pathlib import Path
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.contrib.admin.sites import site
from django.core.files.uploadedfile import SimpleUploadedFile

from discord_tts.voices.admin import VoiceAdmin
from discord_tts.voices.interface import reset_voice_cache
from discord_tts.voices.models import Voice
from discord_tts.voices.tasks import generate_safetensors


@pytest.mark.django_db
class TestVoiceCacheInvalidation:
    def test_voice_save_new_audio_source_resets_cache(self):
        audio_file = SimpleUploadedFile(
            "test.ogg",
            b"audio data",
            content_type="audio/ogg",
        )
        with patch("discord_tts.speech.tasks.reset_voice_cache") as mock_reset:
            voice = Voice.objects.create(
                name="new_voice",
                guild_id=123,
                audio_source=audio_file,
            )
            mock_reset.assert_called_with(voice.pk)

    def test_voice_save_clears_old_processed_safetensor_on_new_audio(self):
        old_audio = SimpleUploadedFile(
            "old.ogg",
            b"old audio",
            content_type="audio/ogg",
        )
        old_st = SimpleUploadedFile(
            "old.safetensors",
            b"old st",
            content_type="application/octet-stream",
        )

        voice = Voice.objects.create(
            name="voice_to_update",
            guild_id=123,
            audio_source=old_audio,
            processed_safetensor=old_st,
        )
        assert voice.processed_safetensor.name is not None

        new_audio = SimpleUploadedFile(
            "new.ogg",
            b"new audio",
            content_type="audio/ogg",
        )
        with patch("discord_tts.speech.tasks.reset_voice_cache") as mock_reset:
            voice.audio_source = new_audio
            voice.save()

            mock_reset.assert_called_with(voice.pk)
            # Old safetensor should be cleared on the instance
            voice.refresh_from_db()
            assert not voice.processed_safetensor

    def test_voice_save_without_new_audio_does_not_reset_cache(self):
        audio_file = SimpleUploadedFile(
            "stable.ogg",
            b"audio data",
            content_type="audio/ogg",
        )
        voice = Voice.objects.create(
            name="initial_name",
            guild_id=123,
            audio_source=audio_file,
        )

        with patch("discord_tts.speech.tasks.reset_voice_cache") as mock_reset:
            voice.name = "renamed_voice"
            voice.save()
            mock_reset.assert_not_called()

    def test_voice_regenerate_safetensors_resets_cache_and_dispatches_task(self):
        audio_file = SimpleUploadedFile(
            "sample.ogg",
            b"audio data",
            content_type="audio/ogg",
        )
        voice = Voice.objects.create(
            name="regen_voice",
            guild_id=123,
            audio_source=audio_file,
        )

        with (
            patch("discord_tts.speech.tasks.reset_voice_cache") as mock_reset,
            patch("discord_tts.voices.tasks.generate_safetensors.delay") as mock_delay,
        ):
            voice.regenerate_safetensors()
            mock_reset.assert_called_once_with(voice.pk)
            mock_delay.assert_called_once_with(voice.pk)

    def test_voice_regenerate_safetensors_refuses_builtin(self):
        voice = Voice.objects.create(name="builtin", guild_id=0)
        with (
            patch("discord_tts.speech.tasks.reset_voice_cache") as mock_reset,
            patch("discord_tts.voices.tasks.generate_safetensors.delay") as mock_delay,
        ):
            voice.regenerate_safetensors()
            mock_reset.assert_not_called()
            mock_delay.assert_not_called()

    def test_voice_delete_resets_cache(self):
        voice = Voice.objects.create(name="delete_me", guild_id=123)
        voice_pk = voice.pk

        with patch("discord_tts.speech.tasks.reset_voice_cache") as mock_reset:
            voice.delete()
            mock_reset.assert_called_once_with(voice_pk)

    def test_generate_safetensors_task_resets_cache_on_success(self):
        audio_file = SimpleUploadedFile(
            "audio.ogg",
            b"dummy audio",
            content_type="audio/ogg",
        )
        voice = Voice.objects.create(
            name="task_voice",
            guild_id=123,
            audio_source=audio_file,
        )

        mock_model = MagicMock()
        mock_model.get_state_for_audio_prompt.return_value = {"tensor": "state"}

        def fake_export(_state, path):
            Path(path).write_bytes(b"dummy safetensors")

        with (
            patch("discord_tts.voices.tasks.get_model", return_value=mock_model),
            patch(
                "discord_tts.voices.tasks.export_model_state",
                side_effect=fake_export,
            ),
            patch("discord_tts.speech.tasks.reset_voice_cache") as mock_reset,
        ):
            generate_safetensors(voice.pk)
            mock_reset.assert_called_with(voice.pk)

    def test_generate_safetensors_task_resets_cache_on_failure(self):
        audio_file = SimpleUploadedFile(
            "fail.ogg",
            b"dummy audio",
            content_type="audio/ogg",
        )
        voice = Voice.objects.create(
            name="fail_voice",
            guild_id=123,
            audio_source=audio_file,
        )

        with (
            patch(
                "discord_tts.voices.tasks.get_model",
                side_effect=RuntimeError("GPU OOM"),
            ),
            patch("discord_tts.speech.tasks.reset_voice_cache") as mock_reset,
            pytest.raises(RuntimeError, match="GPU OOM"),
        ):
            generate_safetensors(voice.pk)

        mock_reset.assert_called_with(voice.pk)

    def test_interface_reset_voice_cache_delegates(self):
        with patch("discord_tts.speech.tasks.reset_voice_cache") as mock_reset:
            reset_voice_cache(99)
            mock_reset.assert_called_once_with(99)

    def test_voice_admin_regenerate_safetensors_action(self):
        audio_file = SimpleUploadedFile(
            "admin.ogg",
            b"dummy audio",
            content_type="audio/ogg",
        )
        voice = Voice.objects.create(
            name="admin_voice",
            guild_id=123,
            audio_source=audio_file,
        )

        voice_admin = VoiceAdmin(Voice, site)
        queryset = Voice.objects.filter(pk=voice.pk)

        with patch.object(Voice, "regenerate_safetensors") as mock_regen:
            voice_admin.regenerate_safetensors(request=MagicMock(), queryset=queryset)
            mock_regen.assert_called_once()
