# discord-tts

A Discord bot providing Text-to-Speech (TTS) in voice channels using [Pocket-TTS](https://github.com/kyutai-labs/pocket-tts) for fast, CPU based inference.

## Features

- No GPU needed!
- Voice cloning!
- Use Django's built-in admin pages to manage voices and restrict user access!
- Automatic TTS for muted users (if configured with message intent)!

## Running the Bot

### Linux/WSL

#### Docker Compose

- Make sure docker is installed
- Use the `docker-compose.prod.yml` file as a guide to deploy it.
- If you cloned the repository, use `docker-compose.local.yml` to build and deploy it.

#### Local/Development

- Make sure docker and uv is installed
- Use the regular `docker-compose.yml` for Redis.
- `uv sync`
- `make migrate`
- `make dev`

### Windows

[Download WSL2](https://learn.microsoft.com/en-us/windows/wsl/install), then follow the instructions above.

## Voice Cloning & Permissions

- You must log into HuggingFace and accept the agreement in the [model page](https://huggingface.co/kyutai/pocket-tts). Then, provide HF_TOKEN as an environment variable.
- Add new voices by logging into the admin panel and using that to upload audio files.
- By default, Django's admin will be on `/admin` on port 8000. If the DJANGO_SUPERUSER_USERNAME and DJANGO_SUPERUSER_PASSWORD env variables are filled in, then it will automatically create an admin user of those types.

### Limiting Voices to Specific Users

Voices can be restricted to specific Discord users via the Django Admin panel:

1. Navigate to `/admin` and open **Voices** under the Voices section.
2. Select an existing voice or create a new one.
3. Use the **Allowed users** field:
   - **Empty (default)**: The voice is public and available to everyone in that server (or all servers if `guild_id` is 0).
   - **Selected users**: The voice is restricted exclusively to the selected Discord accounts. Users not on the list will not see the voice in `/voices`, cannot pick it in `/voice`, and cannot trigger it via `/say`.
4. If a user hasn't interacted with the bot yet, their Discord ID can be added under **Discord accounts** in the Common section.

## Dependency & Environment Setup

- Python 3.14+ required
- Install dependencies using `uv`:
  ```bash
  uv sync
  ```
- Install ffmpeg (see [ffmpeg download page](https://ffmpeg.org/download.html))
- Copy the `.env.example` to the `.env` file and fill in the information.

## Bot Commands

- `/join` - Join the voice channel you are in and bind to the current text channel
- `/leave` - Leave the current voice channel
- `/say` - Make the bot speak text (optional: specify a voice)
- `/multi` - Open a modal to play multiple voicelines with different voices
- `/stop` - Stop current playback and clear the queue for the channel
- `/skip` - Skip the current or next message in the queue
- `/settings` - Adjust your personal preferences
- `/voice` - Change your selected voice

Format for `multi` command:

```
<voice_name>: <text>
alba: Hello everyone! How are you doing?
marius: I'm doing good!
```

## Web UI

There's a web ui in Django, hosted in `/` if you run the default server. It's a really simple UI that will allow you to play text outside of Discord. Note that it doesn't have any authentication nor authorization, so do not expose it to the open web!!!

## Links & Resources

- [Pocket-TTS repository](https://github.com/kyutai-labs/pocket-tts)
- [ffmpeg install guides](https://ffmpeg.org/download.html)
- [Discord developer portal](https://discord.com/developers/applications)
- [uv documentation](https://github.com/astral-sh/uv)

## Contributing

Contributions welcome! Please:

- Suggest new features
- Submit bug reports and pull requests
- Help extend functionality

Open an issue or PR on GitHub to get involved.
