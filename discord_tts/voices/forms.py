from django import forms

from discord_tts.voices.models import Voice


class VoiceForm(forms.ModelForm):
    class Meta:
        model = Voice
        fields = ["name", "guild_id", "audio_source"]
