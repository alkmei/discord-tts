import re
import typing

import emoji

if typing.TYPE_CHECKING:
    import discord

# Priority brackets: (threshold, priority) sorted by threshold ascending
_PRIORITY_BRACKETS = [(3, 9), (10, 5)]


def get_priority(count: int) -> int:
    for threshold, priority in _PRIORITY_BRACKETS:
        if count < threshold:
            return priority
    return 1


def clean_tts_text(
    text: str,
    guild: discord.Guild | None,
) -> str:
    """Clean text content for TTS.

    - Replaces URLs with "(insert link here)"
    - Resolves User Mentions to Nicknames
    - Resolves Custom Emojis to their names
    - Resolves Unicode Emojis to spoken words
    """
    content = text

    content = re.sub(r"https?://\S+", "(insert link here)", content)

    # Resolve Mentions <@ID> or <@!ID> to Nicknames
    def replace_mention(match: re.Match[str]) -> str:
        user_id = int(match.group(1))
        if not guild:
            err = "This should not happen in a server"
            raise RuntimeError(err)
        member = guild.get_member(user_id)
        if member:
            return member.display_name
        return "someone"

    content = re.sub(r"<@!?(\d+)>", replace_mention, content)

    # Resolve Custom Emojis <:name:id> or <a:name:id> to "name"
    content = re.sub(r"<a?:([^:]+):\d+>", r" \1 ", content)

    # Resolve Unicode Emojis (🤨 -> face_with_raised_eyebrow)
    # We replace underscores with spaces and remove colons for cleaner TTS
    content = emoji.demojize(content, delimiters=(" ", " "))
    content = content.replace("_", " ").replace(":", "")
    content = " ".join(content.split())

    # Pocket-TTS use to have this bug that cut the first part of a message off.
    # Adding a period was a failsafe, but not sure if that's still needed.
    return "." + content
