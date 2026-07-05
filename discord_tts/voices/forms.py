import soundfile as sf
from django import forms

from .models import Voice
from .validators import ALLOWED_AUDIO_EXTENSIONS

MAX_AUDIO_SIZE_MB = 10
MAX_AUDIO_SIZE = MAX_AUDIO_SIZE_MB * 1024 * 1024


class VoiceForm(forms.ModelForm):
    class Meta:
        model = Voice
        fields = ["name", "guild_id", "audio_source"]
        widgets = {
            "audio_source": forms.FileInput(
                attrs={
                    "accept": "." + ",.".join(ALLOWED_AUDIO_EXTENSIONS),
                },
            ),
        }

    def clean_audio_source(self):
        file = self.cleaned_data.get("audio_source")

        if file:
            if file.size > MAX_AUDIO_SIZE:
                err = f"Audio file is too large (max {MAX_AUDIO_SIZE_MB}MB).\
                      Tip: audio should be no longer than 30 seconds."
                raise forms.ValidationError(err)

            # We wrap this in a try/except because if it's not a valid
            # libsndfile format, soundfile will throw an error.
            try:
                # Seek(0) ensures we read from the start of the uploaded file
                file.seek(0)
                with sf.SoundFile(file) as _:
                    pass
            except Exception as err:
                msg = (
                    "Unsupported or corrupt audio format. "
                    "Please provide a valid libsndfile-compatible file."
                )
                raise forms.ValidationError(msg) from err
            finally:
                file.seek(0)  # Reset pointer for Django's file saver

        return file
