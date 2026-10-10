import os
import time
from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.test import override_settings

from discord_tts.speech.tasks import get_cached_voice_state
from discord_tts.speech.tasks import reset_voice_cache
from discord_tts.voices.models import Voice

EXPECTED_RELOAD_CALLS = 2


@pytest.fixture(autouse=True)
def _clear_cache():
    reset_voice_cache()
    yield
    reset_voice_cache()


@pytest.mark.django_db
class TestVoiceCache:
    def test_get_cached_voice_state_caches_model_state(self, tmp_path):
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            st_file = tmp_path / "123" / "safetensors" / "voice.safetensors"
            st_file.parent.mkdir(parents=True, exist_ok=True)
            st_file.write_bytes(b"dummy safetensors content")

            voice = Voice.objects.create(
                name="test_voice",
                guild_id=123,
            )
            voice.processed_safetensor.name = "123/safetensors/voice.safetensors"
            Voice.objects.filter(pk=voice.pk).update(
                processed_safetensor=voice.processed_safetensor.name,
            )

            mock_model = MagicMock()
            mock_model.get_state_for_audio_prompt.return_value = {"state": "loaded"}

            with patch("discord_tts.speech.tasks.get_model", return_value=mock_model):
                state1 = get_cached_voice_state(voice.pk, guild_id=123)
                assert state1 == {"state": "loaded"}
                assert mock_model.get_state_for_audio_prompt.call_count == 1

                # Second call: hits cache
                state2 = get_cached_voice_state(voice.pk, guild_id=123)
                assert state2 == {"state": "loaded"}
                assert mock_model.get_state_for_audio_prompt.call_count == 1

    def test_reset_voice_cache_clears_cache(self, tmp_path):
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            st_file = tmp_path / "123" / "safetensors" / "voice.safetensors"
            st_file.parent.mkdir(parents=True, exist_ok=True)
            st_file.write_bytes(b"dummy safetensors content")

            voice = Voice.objects.create(
                name="test_voice",
                guild_id=123,
            )
            voice.processed_safetensor.name = "123/safetensors/voice.safetensors"
            Voice.objects.filter(pk=voice.pk).update(
                processed_safetensor=voice.processed_safetensor.name,
            )

            mock_model = MagicMock()
            mock_model.get_state_for_audio_prompt.return_value = {"state": "loaded"}

            with patch("discord_tts.speech.tasks.get_model", return_value=mock_model):
                get_cached_voice_state(voice.pk, guild_id=123)
                assert mock_model.get_state_for_audio_prompt.call_count == 1

                reset_voice_cache(voice.pk)

                get_cached_voice_state(voice.pk, guild_id=123)
                assert (
                    mock_model.get_state_for_audio_prompt.call_count
                    == EXPECTED_RELOAD_CALLS
                )

    def test_cache_reloads_when_safetensors_file_modified(self, tmp_path):
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            st_file = tmp_path / "123" / "safetensors" / "voice.safetensors"
            st_file.parent.mkdir(parents=True, exist_ok=True)
            st_file.write_bytes(b"dummy safetensors content")

            voice = Voice.objects.create(
                name="test_voice",
                guild_id=123,
            )
            voice.processed_safetensor.name = "123/safetensors/voice.safetensors"
            Voice.objects.filter(pk=voice.pk).update(
                processed_safetensor=voice.processed_safetensor.name,
            )

            mock_model = MagicMock()
            mock_model.get_state_for_audio_prompt.side_effect = [
                {"state": "first"},
                {"state": "second"},
            ]

            with patch("discord_tts.speech.tasks.get_model", return_value=mock_model):
                state1 = get_cached_voice_state(voice.pk, guild_id=123)
                assert state1 == {"state": "first"}
                assert mock_model.get_state_for_audio_prompt.call_count == 1

                # Update file and modify mtime
                st_file.write_bytes(b"updated safetensors content")
                new_mtime = time.time() + 10
                os.utime(str(st_file), (new_mtime, new_mtime))

                # Without manual reset, detects mtime change
                state2 = get_cached_voice_state(voice.pk, guild_id=123)
                assert state2 == {"state": "second"}
                assert (
                    mock_model.get_state_for_audio_prompt.call_count
                    == EXPECTED_RELOAD_CALLS
                )

    def test_cache_reloads_when_safetensors_path_changes(self, tmp_path):
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            st_dir = tmp_path / "123" / "safetensors"
            st_dir.mkdir(parents=True, exist_ok=True)
            file1 = st_dir / "voice_v1.safetensors"
            file1.write_bytes(b"v1")
            file2 = st_dir / "voice_v2.safetensors"
            file2.write_bytes(b"v2")

            voice = Voice.objects.create(
                name="test_voice",
                guild_id=123,
            )
            voice.processed_safetensor.name = "123/safetensors/voice_v1.safetensors"
            Voice.objects.filter(pk=voice.pk).update(
                processed_safetensor=voice.processed_safetensor.name,
            )

            mock_model = MagicMock()
            mock_model.get_state_for_audio_prompt.side_effect = [
                {"state": "v1"},
                {"state": "v2"},
            ]

            with patch("discord_tts.speech.tasks.get_model", return_value=mock_model):
                state1 = get_cached_voice_state(voice.pk, guild_id=123)
                assert state1 == {"state": "v1"}

                # Update voice in DB with new safetensor file path
                Voice.objects.filter(pk=voice.pk).update(
                    processed_safetensor="123/safetensors/voice_v2.safetensors",
                )

                state2 = get_cached_voice_state(voice.pk, guild_id=123)
                assert state2 == {"state": "v2"}
                assert (
                    mock_model.get_state_for_audio_prompt.call_count
                    == EXPECTED_RELOAD_CALLS
                )

    def test_guild_validation_returns_default(self):
        voice = Voice.objects.create(name="guild_voice", guild_id=111)
        mock_model = MagicMock()
        mock_model.get_state_for_audio_prompt.return_value = {"state": "alba"}

        with patch("discord_tts.speech.tasks.get_model", return_value=mock_model):
            state = get_cached_voice_state(voice.pk, guild_id=222)
            assert state == {"state": "alba"}
            mock_model.get_state_for_audio_prompt.assert_called_once_with("alba")

    def test_builtin_voice_loads_by_name(self):
        voice, _ = Voice.objects.get_or_create(name="alba", guild_id=0)
        mock_model = MagicMock()
        mock_model.get_state_for_audio_prompt.return_value = {"state": "builtin"}

        with patch("discord_tts.speech.tasks.get_model", return_value=mock_model):
            state = get_cached_voice_state(voice.pk, guild_id=999)
            assert state == {"state": "builtin"}
            mock_model.get_state_for_audio_prompt.assert_called_once_with("alba")

    def test_fallback_to_audio_source_when_safetensor_missing(self, tmp_path):
        with override_settings(MEDIA_ROOT=str(tmp_path)):
            audio_dir = tmp_path / "123" / "voices"
            audio_dir.mkdir(parents=True, exist_ok=True)
            audio_file = audio_dir / "voice.ogg"
            audio_file.write_bytes(b"dummy ogg")

            voice = Voice.objects.create(name="voice_no_st", guild_id=123)
            voice.processed_safetensor.name = "123/safetensors/nonexistent.safetensors"
            voice.audio_source.name = "123/voices/voice.ogg"
            Voice.objects.filter(pk=voice.pk).update(
                processed_safetensor=voice.processed_safetensor.name,
                audio_source=voice.audio_source.name,
            )

            mock_model = MagicMock()
            mock_model.get_state_for_audio_prompt.return_value = {"state": "from_audio"}

            with patch("discord_tts.speech.tasks.get_model", return_value=mock_model):
                state = get_cached_voice_state(voice.pk, guild_id=123)
                assert state == {"state": "from_audio"}
                mock_model.get_state_for_audio_prompt.assert_called_once_with(
                    str(audio_file),
                )

    def test_cache_clear_alias_on_get_cached_voice_state(self):
        assert hasattr(get_cached_voice_state, "cache_clear")
        assert hasattr(get_cached_voice_state, "cache_info")
        get_cached_voice_state.cache_clear()
        info = get_cached_voice_state.cache_info()
        assert info.currsize == 0
