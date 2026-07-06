import pytest

from discord_tts.common.models import DiscordAccount
from discord_tts.preferences.interface import UserPreferenceUpdateData
from discord_tts.preferences.interface import get_user_preferences
from discord_tts.preferences.interface import update_user_preferences
from discord_tts.preferences.interface import update_user_voice
from discord_tts.preferences.models import UserGuildPreferences
from discord_tts.voices.models import Voice


@pytest.fixture
def voice():
    """Create a Voice instance in the database."""
    account = DiscordAccount.objects.create(discord_id=999999999999999999)
    v = Voice.objects.create(name="TestVoice", guild_id=200200200200200200)
    v.allowed_users.add(account)
    return v


@pytest.mark.django_db
class TestUpdateUserPreferences:
    def test_creates_preferences_when_none_exist(self):
        discord_id = 111111111111111111
        guild_id = 222222222222222222
        data: UserPreferenceUpdateData = {
            "introduce_speaker": True,
            "speak_while_muted": False,
        }

        success, prefs = update_user_preferences(discord_id, guild_id, data)

        assert success is True
        assert prefs.account.discord_id == discord_id
        assert prefs.guild_id == guild_id
        assert prefs.introduce_speaker is True
        assert prefs.speak_while_muted is False
        assert prefs.echo_say_command is True  # default

    def test_updates_existing_preferences(self):
        discord_id = 333333333333333333
        guild_id = 444444444444444444

        original = UserGuildPreferences.objects.create(
            account=DiscordAccount.objects.create(discord_id=discord_id),
            guild_id=guild_id,
            introduce_speaker=False,
            echo_say_command=False,
        )

        data: UserPreferenceUpdateData = {"introduce_speaker": True}
        success, prefs = update_user_preferences(discord_id, guild_id, data)

        assert success is True
        assert prefs.pk == original.pk
        assert prefs.introduce_speaker is True
        assert prefs.echo_say_command is False  # unchanged

    def test_all_fields_can_be_updated(self):
        discord_id = 555555555555555555
        guild_id = 666666666666666666
        data: UserPreferenceUpdateData = {
            "introduce_speaker": True,
            "speak_while_muted": False,
            "echo_say_command": False,
        }

        _, prefs = update_user_preferences(discord_id, guild_id, data)

        assert prefs.introduce_speaker is True
        assert prefs.speak_while_muted is False
        assert prefs.echo_say_command is False

    def test_empty_data_returns_default_prefs(self):
        discord_id = 777777777777777777
        guild_id = 888888888888888888

        success, prefs = update_user_preferences(discord_id, guild_id, {})

        assert success is True
        assert isinstance(prefs, UserGuildPreferences)

    def test_different_guilds_have_separate_preferences(self):
        discord_id = 999999999999999999
        guild_one = 101010101010101010
        guild_two = 202020202020202020

        data: UserPreferenceUpdateData = {"introduce_speaker": True}
        update_user_preferences(discord_id, guild_one, data)

        _, prefs_guild_two = update_user_preferences(discord_id, guild_two, {})

        assert prefs_guild_two.introduce_speaker is False  # default for new guild

    def test_partial_update_preserves_other_fields(self):
        discord_id = 123123123123123123
        guild_id = 456456456456456456

        UserGuildPreferences.objects.create(
            account=DiscordAccount.objects.create(discord_id=discord_id),
            guild_id=guild_id,
            introduce_speaker=False,
            speak_while_muted=False,
            echo_say_command=False,
        )

        data: UserPreferenceUpdateData = {"speak_while_muted": True}
        _, prefs = update_user_preferences(discord_id, guild_id, data)

        assert prefs.speak_while_muted is True
        assert prefs.introduce_speaker is False
        assert prefs.echo_say_command is False


def _create_voice(
    name: str,
    guild_id: int,
    account: DiscordAccount | None = None,
) -> Voice:
    v = Voice.objects.create(name=name, guild_id=guild_id)
    if account:
        v.allowed_users.add(account)
    return v


@pytest.mark.django_db
class TestUpdateUserVoice:
    def test_updates_voice_successfully(self):
        discord_id = 100100100100100100
        guild_id = 200200200200200200
        account = DiscordAccount.objects.create(discord_id=discord_id)
        voice = _create_voice("TestVoice", guild_id, account)

        result = update_user_voice(discord_id, guild_id, voice.pk)

        assert result == "TestVoice"

        prefs = UserGuildPreferences.objects.get(
            account__discord_id=discord_id,
            guild_id=guild_id,
        )
        assert prefs.voice == voice

    def test_returns_none_when_voice_not_found(self):
        discord_id = 300300300300300300
        guild_id = 400400400400400400
        DiscordAccount.objects.create(discord_id=discord_id)

        result = update_user_voice(discord_id, guild_id, 999)

        assert result is None

    def test_overwrites_existing_voice(self):
        discord_id = 700700700700700700
        guild_id = 800800800800800800
        account = DiscordAccount.objects.create(discord_id=discord_id)

        old_voice = _create_voice("OldVoice", guild_id, account)
        new_voice = _create_voice("NewVoice", guild_id, account)

        UserGuildPreferences.objects.create(
            account=account,
            guild_id=guild_id,
            voice=old_voice,
        )

        result = update_user_voice(discord_id, guild_id, new_voice.pk)

        assert result == "NewVoice"
        prefs = UserGuildPreferences.objects.get(
            account__discord_id=discord_id,
            guild_id=guild_id,
        )
        assert prefs.voice == new_voice


@pytest.mark.django_db
class TestGetUserPreferences:
    def test_returns_existing_preferences(self):
        discord_id = 110110110110110110
        guild_id = 210210210210210210

        existing = UserGuildPreferences.objects.create(
            account=DiscordAccount.objects.create(discord_id=discord_id),
            guild_id=guild_id,
            introduce_speaker=True,
            speak_while_muted=False,
            echo_say_command=True,
        )

        prefs = get_user_preferences(discord_id, guild_id)

        assert prefs.pk == existing.pk
        assert prefs.introduce_speaker is True
        assert prefs.speak_while_muted is False

    def test_creates_preferences_when_none_exist(self):
        discord_id = 310310310310310310
        guild_id = 410410410410410410

        prefs = get_user_preferences(discord_id, guild_id)

        assert isinstance(prefs, UserGuildPreferences)
        assert prefs.account.discord_id == discord_id
        assert prefs.guild_id == guild_id
        assert prefs.introduce_speaker is False
        assert prefs.speak_while_muted is True  # default
        assert prefs.echo_say_command is True  # default

    def test_different_guilds_return_different_preferences(self):
        guild_one = 810810810810810810
        guild_two = 910910910910910910

        prefs_one = get_user_preferences(101010101010101010, guild_one)
        prefs_two = get_user_preferences(202020202020202020, guild_two)

        assert prefs_one.account.discord_id != prefs_two.account.discord_id

    def test_same_guild_same_account_returns_same_record(self):
        discord_id = 303030303030303030
        guild_id = 404040404040404040

        prefs_one = get_user_preferences(discord_id, guild_id)
        prefs_two = get_user_preferences(discord_id, guild_id)

        assert prefs_one.pk == prefs_two.pk
        assert prefs_one.introduce_speaker == prefs_two.introduce_speaker
        assert prefs_one.speak_while_muted == prefs_two.speak_while_muted
        assert prefs_one.echo_say_command == prefs_two.echo_say_command

    def test_same_user_different_accounts_separated(self):
        discord_id = 121212121212121212
        guild_one = 131313131313131313
        guild_two = 141414141414141414

        UserGuildPreferences.objects.create(
            account=DiscordAccount.objects.create(discord_id=discord_id),
            guild_id=guild_one,
            introduce_speaker=True,
        )

        UserGuildPreferences.objects.create(
            account=DiscordAccount.objects.create(discord_id=discord_id + 1),
            guild_id=guild_two,
            introduce_speaker=False,
        )

        prefs_one = get_user_preferences(discord_id, guild_one)
        prefs_two = get_user_preferences(discord_id + 1, guild_two)

        assert prefs_one.introduce_speaker is True
        assert prefs_two.introduce_speaker is False

    def test_default_values_are_correct(self):
        discord_id = 151515151515151515
        guild_id = 161616161616161616

        prefs = get_user_preferences(discord_id, guild_id)

        assert prefs.introduce_speaker is False
        assert prefs.speak_while_muted is True
        assert prefs.echo_say_command is True
