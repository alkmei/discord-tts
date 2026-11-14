import pytest
from django.contrib.admin.sites import AdminSite
from django.core.files.uploadedfile import SimpleUploadedFile

from discord_tts.common.models import DiscordAccount
from discord_tts.voices.admin import VoiceAdmin
from discord_tts.voices.forms import VoiceForm
from discord_tts.voices.interface import get_available_voices
from discord_tts.voices.interface import get_voice
from discord_tts.voices.models import Voice


@pytest.mark.django_db
class TestVoicePermissions:
    def test_voice_admin_access_status(self):
        admin = VoiceAdmin(Voice, AdminSite())
        voice = Voice.objects.create(name="test_voice", guild_id=123)
        assert admin.access_status(voice) == "Public"

        user = DiscordAccount.objects.create(discord_id=1001)
        voice.allowed_users.add(user)
        assert admin.access_status(voice) == "Restricted (1 user)"

        user2 = DiscordAccount.objects.create(discord_id=1002)
        voice.allowed_users.add(user2)
        assert admin.access_status(voice) == "Restricted (2 users)"

    def test_voice_form_with_allowed_users(self):
        user = DiscordAccount.objects.create(discord_id=1001)
        audio = SimpleUploadedFile("voice.ogg", b"audio", content_type="audio/ogg")
        form = VoiceForm(
            data={
                "name": "form_voice",
                "guild_id": 123,
                "allowed_users": [user.pk],
            },
            files={"audio_source": audio},
        )
        assert form.is_valid(), form.errors
        voice = form.save()
        assert list(voice.allowed_users.all()) == [user]

    def test_get_available_voices_respects_whitelist(self):
        user_allowed = DiscordAccount.objects.create(discord_id=111)
        DiscordAccount.objects.create(discord_id=222)

        public_voice = Voice.objects.create(name="public_voice", guild_id=123)
        private_voice = Voice.objects.create(name="private_voice", guild_id=123)
        private_voice.allowed_users.add(user_allowed)

        # Allowed user sees both public and whitelisted voice
        voices_for_allowed = get_available_voices(discord_id=111, guild_id=123)
        voice_ids_for_allowed = {v.pk for v in voices_for_allowed}
        assert public_voice.pk in voice_ids_for_allowed
        assert private_voice.pk in voice_ids_for_allowed

        # Forbidden user only sees public voice
        voices_for_forbidden = get_available_voices(discord_id=222, guild_id=123)
        voice_ids_for_forbidden = {v.pk for v in voices_for_forbidden}
        assert public_voice.pk in voice_ids_for_forbidden
        assert private_voice.pk not in voice_ids_for_forbidden

        # get_voice respects permission
        assert (
            get_voice(discord_id=111, guild_id=123, voice_pk=private_voice.pk)
            is not None
        )
        assert (
            get_voice(discord_id=222, guild_id=123, voice_pk=private_voice.pk)
            is None
        )
