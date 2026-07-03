from django.contrib import admin
from django.utils.html import format_html

from apps.voices.forms import VoiceForm

from .models import Voice


@admin.display(
    description="processed_safetensor",
)
def make_processed_safetensor_link(voice: Voice) -> str:
    if voice.processed_safetensor:
        return format_html(
            '<a href="{}" target="_blank">Download</a>',
            voice.processed_safetensor.url,
        )
    return "—"


@admin.register(Voice)
class VoiceAdmin(admin.ModelAdmin):
    form = VoiceForm
    list_display = (
        "name",
        "guild_id",
        "audio_source",
        "processed_safetensor",
    )
    list_filter = ("guild_id",)
    search_fields = ("name",)
    actions = ["regenerate_safetensors"]

    @admin.action(description="Regenerate safetensor for selected voice(s)")
    def regenerate_safetensors(self, request, queryset):
        for voice in queryset:
            voice.regenerate_safetensors()
