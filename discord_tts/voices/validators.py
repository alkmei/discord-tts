from django.core.validators import FileExtensionValidator

# All formats that soundfile supports
ALLOWED_AUDIO_EXTENSIONS = [
    "wav",
    "aiff",
    "aif",
    "au",
    "snd",
    "raw",
    "paf",
    "svx",
    "nist",
    "sph",
    "voc",
    "ircam",
    "sf",
    "w64",
    "mat",
    "pvf",
    "xi",
    "htk",
    "sds",
    "avr",
    "sd2",
    "flac",
    "caf",
    "wve",
    "ogg",
    "oga",
    "mpc",
    "rf64",
    "mp3",
]

audio_extension_validator = FileExtensionValidator(
    allowed_extensions=ALLOWED_AUDIO_EXTENSIONS,
)
