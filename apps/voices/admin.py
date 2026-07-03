from django.contrib import admin
from django.utils.html import format_html

from apps.voices.forms import VoiceForm

from .models import Voice


def make_processed_safetensor_link(voice: Voice) -> str:
    if voice.processed_safetensor:
        return format_html(
            '<a href="{}" target="_blank">Download</a>',
            voice.processed_safetensor.url,
        )
    return "—"


make_processed_safetensor_link.short_description = "processed_safetensor"


@admin.register(Voice)
class VoiceAdmin(admin.ModelAdmin):
    form = VoiceForm
    list_display = (
        "name",
        "guild_id",
        "audio_source_link",
        "processed_safetensor",
    )
    list_filter = ("guild_id",)
    search_fields = ("name",)

    def audio_source_link(self, voice: Voice) -> str:
        if voice.audio_source:
            return format_html(
                '<a href="{}" target="_blank">Download</a>',
                voice.audio_source.url,
            )
        return "—"

    audio_source_link.short_description = "audio_source"
