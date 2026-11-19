from unittest.mock import MagicMock

from bot.services.tts_service import resolve_mentions
from discord_tts.speech.utils import resolve_mentions_agnostic


def test_resolve_mentions_agnostic():
    member_map = {111: "Alice", 222: "Bob"}
    role_map = {333: "Moderator", 444: "VIP"}
    channel_map = {555: "general", 666: "bot-commands"}

    text = (
        "Hello <@111> and <@!222>, check <#555> or <#666>. "
        "Ask <@&333> and <@&444>."
    )

    resolved = resolve_mentions_agnostic(
        text,
        member_map=member_map,
        role_map=role_map,
        channel_map=channel_map,
    )

    assert resolved == (
        "Hello @Alice and @Bob, check #general or #bot-commands. "
        "Ask @Moderator and @VIP."
    )


def test_resolve_mentions_agnostic_defaults_and_fallbacks():
    # When maps are empty or IDs are not found
    text = "<@123> <@!456> <@&789> <#101112> normal text"
    resolved = resolve_mentions_agnostic(text)
    assert resolved == "@someone @someone @role #channel normal text"


def test_resolve_mentions_with_guild():
    guild = MagicMock()

    member1 = MagicMock()
    member1.id = 1001
    member1.display_name = "Charlie"

    role1 = MagicMock()
    role1.id = 2001
    role1.name = "Admins"

    channel1 = MagicMock()
    channel1.id = 3001
    channel1.name = "announcements"

    thread1 = MagicMock()
    thread1.id = 4001
    thread1.name = "patch-notes"

    guild.members = [member1]
    guild.roles = [role1]
    guild.channels = [channel1]
    guild.threads = [thread1]

    text = "Hey <@1001>, check <@&2001> in <#3001> and thread <#4001>!"
    result = resolve_mentions(text, guild)

    assert (
        result
        == "Hey @Charlie, check @Admins in #announcements and thread #patch-notes!"
    )
