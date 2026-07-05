from django.apps import AppConfig


class VoicesConfig(AppConfig):
    name = "discord_tts.voices"

    def ready(self) -> None:
        import discord_tts.voices.tasks  # noqa: F401, PLC0415
