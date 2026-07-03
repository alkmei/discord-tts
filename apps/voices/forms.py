from django import forms

from apps.voices.models import Voice
from apps.voices.tasks import generate_safetensors


class VoiceForm(forms.ModelForm):
    class Meta:
        model = Voice
        fields = "__all__"

    def save(self, commit=True):
        obj = super().save(commit)

        if obj.audio_source and not obj.processed_safetensor:
            audio_path = obj.audio_source.path
            generate_safetensors.delay(obj.id, audio_path)

        return obj
