import pytest
from django.contrib.admin.sites import site
from django.db import IntegrityError

from discord_tts.common.models import DiscordAccount
from discord_tts.preferences.admin import UserGuildPreferencesAdmin
from discord_tts.preferences.interface import get_user_preferences
from discord_tts.preferences.models import UserGuildPreferences

EXPECTED_COUNT = 2


@pytest.mark.django_db
class TestUserGuildPreferencesModel:
    def test_unique_per_account_and_guild(self):
        account = DiscordAccount.objects.create(discord_id=123456789012345678)
        guild_id = 111222333444555666

        UserGuildPreferences.objects.create(
            account=account,
            guild_id=guild_id,
        )

        with pytest.raises(IntegrityError):
            UserGuildPreferences.objects.create(
                account=account,
                guild_id=guild_id,
            )

    def test_same_user_different_guilds(self):
        account = DiscordAccount.objects.create(discord_id=123456789012345678)
        guild_one = 111222333444555666
        guild_two = 777888999000111222

        pref_one = UserGuildPreferences.objects.create(
            account=account,
            guild_id=guild_one,
        )
        pref_two = UserGuildPreferences.objects.create(
            account=account,
            guild_id=guild_two,
        )

        assert pref_one.pk != pref_two.pk
        assert (
            UserGuildPreferences.objects.filter(account=account).count()
            == EXPECTED_COUNT
        )

    def test_different_users_same_guild(self):
        account_one = DiscordAccount.objects.create(discord_id=111111111111111111)
        account_two = DiscordAccount.objects.create(discord_id=222222222222222222)
        guild_id = 999999999999999999

        pref_one = UserGuildPreferences.objects.create(
            account=account_one,
            guild_id=guild_id,
        )
        pref_two = UserGuildPreferences.objects.create(
            account=account_two,
            guild_id=guild_id,
        )

        assert pref_one.pk != pref_two.pk
        assert (
            UserGuildPreferences.objects.filter(guild_id=guild_id).count()
            == EXPECTED_COUNT
        )

    def test_get_or_create_creates_new_row_for_unique_user_guild(self):
        account = DiscordAccount.objects.create(discord_id=123456789012345678)
        guild_id = 111222333444555666

        pref, created = UserGuildPreferences.objects.get_or_create(
            account=account,
            guild_id=guild_id,
        )

        assert created is True
        assert pref.account == account
        assert pref.guild_id == guild_id
        assert (
            UserGuildPreferences.objects.filter(
                account=account, guild_id=guild_id,
            ).count()
            == 1
        )

    def test_get_or_create_returns_existing_row_for_duplicate_user_guild(self):
        account = DiscordAccount.objects.create(discord_id=123456789012345678)
        guild_id = 111222333444555666

        pref_first, created_first = UserGuildPreferences.objects.get_or_create(
            account=account,
            guild_id=guild_id,
        )
        pref_second, created_second = UserGuildPreferences.objects.get_or_create(
            account=account,
            guild_id=guild_id,
        )

        assert created_first is True
        assert created_second is False
        assert pref_first.pk == pref_second.pk
        assert (
            UserGuildPreferences.objects.filter(
                account=account, guild_id=guild_id,
            ).count()
            == 1
        )

    def test_get_or_create_creates_new_row_when_same_user_in_new_guild(self):
        account = DiscordAccount.objects.create(discord_id=123456789012345678)
        guild_one = 111222333444555666
        guild_two = 777888999000111222

        pref_one, created_one = UserGuildPreferences.objects.get_or_create(
            account=account,
            guild_id=guild_one,
        )
        pref_two, created_two = UserGuildPreferences.objects.get_or_create(
            account=account,
            guild_id=guild_two,
        )

        assert created_one is True
        assert created_two is True
        assert pref_one.pk != pref_two.pk
        assert (
            UserGuildPreferences.objects.filter(account=account).count()
            == EXPECTED_COUNT
        )

    def test_get_or_create_creates_new_row_when_different_user_in_same_guild(self):
        account_one = DiscordAccount.objects.create(discord_id=111111111111111111)
        account_two = DiscordAccount.objects.create(discord_id=222222222222222222)
        guild_id = 999999999999999999

        pref_one, created_one = UserGuildPreferences.objects.get_or_create(
            account=account_one,
            guild_id=guild_id,
        )
        pref_two, created_two = UserGuildPreferences.objects.get_or_create(
            account=account_two,
            guild_id=guild_id,
        )

        assert created_one is True
        assert created_two is True
        assert pref_one.pk != pref_two.pk
        assert (
            UserGuildPreferences.objects.filter(guild_id=guild_id).count()
            == EXPECTED_COUNT
        )

    def test_index_and_constraint_configured(self):
        meta = UserGuildPreferences._meta  # noqa: SLF001
        index_fields = [tuple(idx.fields) for idx in meta.indexes]
        assert ("account", "guild_id") in index_fields

        constraint_fields = [
            tuple(c.fields) for c in meta.constraints if hasattr(c, "fields")
        ]
        assert ("account", "guild_id") in constraint_fields


@pytest.mark.django_db
class TestUserGuildPreferencesInterface:
    def test_get_user_preferences_creates_row_for_unique_user_guild(self):
        discord_id = 123456789012345678
        guild_id = 111222333444555666

        assert UserGuildPreferences.objects.count() == 0

        prefs, _admin_prefs = get_user_preferences(discord_id, guild_id)

        assert UserGuildPreferences.objects.count() == 1
        created_pref = UserGuildPreferences.objects.get()
        assert created_pref.account.discord_id == discord_id
        assert created_pref.guild_id == guild_id
        assert prefs["speak_while_muted"] is True
        assert prefs["echo_say_command"] is True

    def test_get_user_preferences_creates_new_row_for_second_guild_without_error(self):
        discord_id = 123456789012345678
        guild_one = 111222333444555666
        guild_two = 777888999000111222

        get_user_preferences(discord_id, guild_one)
        assert UserGuildPreferences.objects.count() == 1

        # Calling for a second guild for the same user should create a second row,
        # not raise MultipleObjectsReturned
        get_user_preferences(discord_id, guild_two)
        assert UserGuildPreferences.objects.count() == EXPECTED_COUNT

        # Calling again for the first guild should return existing without adding a row
        get_user_preferences(discord_id, guild_one)
        assert UserGuildPreferences.objects.count() == EXPECTED_COUNT


class TestUserGuildPreferencesAdmin:
    def test_admin_configuration(self):
        model_admin = site._registry[UserGuildPreferences]  # noqa: SLF001
        assert isinstance(model_admin, UserGuildPreferencesAdmin)
        assert "account" in model_admin.list_display
        assert "guild_id" in model_admin.list_display
        assert "guild_id" in model_admin.list_filter
        assert "guild_id" in model_admin.search_fields
        assert "account__discord_id" in model_admin.search_fields
