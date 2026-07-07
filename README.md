# discord-tts

A Discord bot providing Text-to-Speech (TTS) in voice channels using [Pocket-TTS](https://github.com/kyutai-labs/pocket-tts) for fast, CPU based inference.

## Features

- No GPU needed!
- Voice cloning!
- Use Django's built-in admin pages to manage voices!
- Automatic TTS for muted users (if configured with message intent)!

## Running the Bot

### Linux/WSL

#### Docker Compose

- Make sure docker is installed
- Use the `docker-compose.prod.yml` file as a guide to deploy it.

#### Local/Development

- Make sure docker and uv is installed
- Use the regular `docker-compose.yml` for Redis.
- `uv sync`
- `make migrate`
- `make dev`

### Windows

[Download WSL2](https://learn.microsoft.com/en-us/windows/wsl/install), then follow the instructions above.

### IMPORTANT

The Django web ui is NOT meant to be facing the open web!!! Do NOT make it face public!!!

## Voice Cloning

- You must log into HuggingFace and accept the agreement in the [model page](https://huggingface.co/kyutai/pocket-tts). Then, provide HF_TOKEN as an environment variable.
- Add new voices by logging into the admin panel and using that to upload audio files.

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
- `/settings` - Adjust your personal preferences (voice, introduce_speaker)

Format for `multi` command:

```
<voice_name>: <text>
alba: Hello everyone! How are you doing?
marius: I'm doing good!
```

## Web UI

There's a web ui in Django, hosted in `/` if you run the default server. It's a really simple UI that will allow you to play text outside of Discord. Note that it doesn't have any protection, so do not expose it to the open web!!!

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
