import pytest

from discord_tts.common.interface import sync_discord_account
from discord_tts.common.models import DiscordAccount


# These tests are kind of useless right now,
# but it's a template if more functionality is added
@pytest.mark.django_db
class TestSyncDiscordAccount:
    def test_creates_new_account(self):
        discord_id = 123456789012345678

        account, created = sync_discord_account(discord_id)

        assert created is True
        assert isinstance(account, DiscordAccount)
        assert account.discord_id == discord_id

        # Verify persistence
        persisted = DiscordAccount.objects.get(discord_id=discord_id)
        assert persisted.discord_id == discord_id

    def test_returns_existing_account_on_sync(self):
        discord_id = 987654321098765432
        DiscordAccount.objects.create(discord_id=discord_id)

        account, created = sync_discord_account(discord_id)

        assert created is False
        assert isinstance(account, DiscordAccount)
        assert account.discord_id == discord_id
        assert account.pk is not None

    def test_creates_unique_accounts(self):
        id_one = 111111111111111111
        id_two = 222222222222222222

        account_one, created_one = sync_discord_account(id_one)
        account_two, created_two = sync_discord_account(id_two)

        assert created_one is True
        assert created_two is True
        assert account_one.discord_id != account_two.discord_id
        assert DiscordAccount.objects.count() == 2

    def test_sync_preserves_existing_primary_key(self):
        discord_id = 333333333333333333
        original_pk = DiscordAccount.objects.create(discord_id=discord_id).pk

        account, created = sync_discord_account(discord_id)

        assert created is False
        assert account.pk == original_pk
        assert DiscordAccount.objects.count() == 1
