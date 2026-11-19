from django.contrib import admin
from django.utils.html import format_html

from discord_tts.speech.tasks import get_cached_voice_state
from discord_tts.voices.forms import VoiceForm

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
    autocomplete_fields = ("allowed_users",)
    list_display = (
        "name",
        "guild_id",
        "audio_source",
        "processed_safetensor",
        "access_status",
    )
    list_filter = ("guild_id",)
    search_fields = ("name",)
    actions = ["regenerate_safetensors"]

    @admin.display(description="Access")
    def access_status(self, voice: Voice) -> str:
        count = voice.allowed_users.count()
        if count == 0:
            return "Public"
        return f"Restricted ({count} user{'s' if count != 1 else ''})"

    @admin.action(description="Regenerate safetensor for selected voice(s)")
    def regenerate_safetensors(self, request, queryset):
        valid_voices = queryset.exclude(guild_id=0)
        for voice in valid_voices:
            voice.regenerate_safetensors()

        get_cached_voice_state.cache_clear()
