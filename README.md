# discord-tts

A Discord bot providing real-time Text-to-Speech (TTS) in voice channels using [Pocket-TTS](https://github.com/kyutai-labs/pocket-tts) for fast, high-quality speech generation. Built with Python for cross-platform compatibility.

## Features

- Uses Django's admin panel for managing voices
- Automatic TTS for muted users

## Running the Bot

### Linux/WSL

- Make sure docker is installed
- Configure `.env` (Discord bot token, etc.)
- `docker compose up`

### Windows

[Download WSL2](https://learn.microsoft.com/en-us/windows/wsl/install), then follow the instructions above.

## Voice Cloning

- Add new voices by logging into the admin panel and using that to upload audio files.
- You must log into HuggingFace and accept the agreement in the [model page](https://huggingface.co/kyutai/pocket-tts). Then, provide HF_TOKEN as an environment variable.

## Dependency & Environment Setup (Summarized)

- Python 3.14+ required
- Install dependencies using `uv`:
  ```bash
  uv sync
  ```
- Install ffmpeg (see [ffmpeg download page](https://ffmpeg.org/download.html))
- Create a `voices` directory and add your models
- Place your Discord bot token and config in a `.env` file

## Bot Commands

- `/join` - Join the voice channel you are in and bind to the current text channel
- `/leave` - Leave the current voice channel
- `/say` - Make the bot speak text (optional: specify a voice)
- `/multi` - Open a modal to play multiple voicelines with different voices
- `/stop` - Stop current playback and clear the queue for the channel
- `/skip` - Skip the current or next message in the queue
- `/settings` - Adjust your personal preferences (voice, introduce_speaker)

Script for `multi` command:

```
alba: Hello everyone! How are you doing?
marius: I'm doing good!
```

- **Automatic TTS:** Muted user’s text messages are spoken aloud in voice channels.

## WebUI

There's a web ui in Django, hosted in `/` if you run the default server. It's a really simple UI that will allow you to play text outside of Discord. Note that it doesn't have any protection, so be cautious when deploying it publicly.

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
