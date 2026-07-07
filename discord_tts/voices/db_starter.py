def add_default_voices(apps, schema_editor):
    Voice = apps.get_model("voices", "Voice")
    english_voices = [
        "alba",
        "anna",
        "azelma",
        "bill_boerst",
        "caro_davy",
        "charles",
        "cosette",
        "eponine",
        "eve",
        "fantine",
        "george",
        "jane",
        "jean",
        "javert",
        "marius",
        "mary",
        "michael",
        "paul",
        "peter_yearsley",
        "stuart_bell",
        "vera",
    ]
    for name in english_voices:
        # Guild 0 marks these as available to everyone
        Voice.objects.get_or_create(name=name, guild_id=0)
