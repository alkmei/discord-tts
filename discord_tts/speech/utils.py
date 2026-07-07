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


def resolve_mentions_agnostic(text: str, member_map: dict[int, str]) -> str:
    """
    Pass a dict of {user_id: display_name} to keep this
    function independent of the discord.py library.
    """

    def replace_mention(match: re.Match[str]) -> str:
        user_id = int(match.group(1))
        return member_map.get(user_id, "someone")

    return re.sub(r"<@!?(\d+)>", replace_mention, text)
