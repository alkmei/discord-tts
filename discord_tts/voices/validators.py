from django.core.validators import FileExtensionValidator

# All formats that soundfile supports
ALLOWED_AUDIO_EXTENSIONS = [
    "mp3",
    "wav",
    "ogg",
    "oga",
    "m4a",
    "aac",
    "wma",
    "opus",
    "flac",
    "alac",
]
audio_extension_validator = FileExtensionValidator(
    allowed_extensions=ALLOWED_AUDIO_EXTENSIONS,
)
