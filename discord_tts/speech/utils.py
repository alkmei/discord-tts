import re

import emoji


def clean_tts_text(text: str) -> str:
    content = text
    content = re.sub(r"https?://\S+", "(insert link here)", content)
    content = re.sub(r"<a?:([^:]+):\d+>", r" \1 ", content)
    content = emoji.demojize(content, delimiters=(" ", " "))
    content = content.replace("_", " ").replace(":", "")
    content = " ".join(content.split())
    return "." + content


def resolve_mentions_agnostic(
    text: str,
    member_map: dict[int, str] | None = None,
    role_map: dict[int, str] | None = None,
    channel_map: dict[int, str] | None = None,
) -> str:
    """Pass dicts of {id: name} to resolve user, role, and channel mentions

    independent of the discord.py library.
    """
    members = member_map or {}
    roles = role_map or {}
    channels = channel_map or {}

    transforms = {
        "@": lambda i: f"@{members.get(i, 'someone')}",
        "@!": lambda i: f"@{members.get(i, 'someone')}",
        "@&": lambda i: f"@{roles.get(i, 'role')}",
        "#": lambda i: f"#{channels.get(i, 'channel')}",
    }

    def replace_mention(match: re.Match[str]) -> str:
        prefix = match.group(1)
        target_id = int(match.group(2))
        transform = transforms.get(prefix)
        return transform(target_id) if transform else match.group(0)

    # Resolve Discord user, role, and channel mentions: <@ID>, <@!ID>, <@&ID>, <#ID>
    return re.sub(r"<(@[!&]?|#)(\d+)>", replace_mention, text)
