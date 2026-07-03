from django.apps import AppConfig


class VoicesConfig(AppConfig):
    name = "apps.voices"

    def ready(self) -> None:
        import apps.voices.signals  # noqa: PLC0415
        import apps.voices.tasks  # noqa: F401, PLC0415
