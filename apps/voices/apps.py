from django.apps import AppConfig


class VoicesConfig(AppConfig):
    name = "apps.voices"

    def ready(self) -> None:
        import apps.voices.signals  # noqa: F401, PLC0415
