from .models import DiscordAccount


def sync_discord_account(discord_id: int) -> tuple[DiscordAccount, bool]:
    """Syncs Discord account with the db"""
    account, created = DiscordAccount.objects.update_or_create(
        discord_id=discord_id,
    )
    return account, created
