from django import forms

from apps.voices.models import Voice


class VoiceForm(forms.ModelForm):
    class Meta:
        model = Voice
        fields = ["name", "guild_id", "audio_source"]
