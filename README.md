# discord-tts

A Discord bot providing real-time Text-to-Speech (TTS) in voice channels using [Pocket-TTS](https://github.com/kyutai-labs/pocket-tts) for fast, high-quality speech generation. Built with Python for cross-platform compatibility; note, the included voice export script is Bash and compatible with Linux/macOS only.

## Features

- Custom voice support via `.safetensors` models (recommended for maximum speed)
- Optional `.wav` voice format (slower)
- Automatic TTS for muted users
- Primary commands: `!voice`, `!s`, `!t`

## Voice System

- Store custom trained voices in a `voices` directory (create this yourself).
- Add new voices by:
  1. Collecting audio samples (`wav`, `mp3`, `flac`, `m4a`, `ogg`, `opus`)
  2. Using [Pocket-TTS](https://github.com/kyutai-labs/pocket-tts) and the `export-voices.sh` script to convert/truncate/export
  3. Placing `.safetensors` files in the `voices` directory
- `.wav` files may be used but are slower; `.safetensors` is strongly recommended.
- No voice listing command yet; inspect the `voices` folder manually.

## Training & Exporting Voices

Use the `export-voices.sh` script to convert supported audio formats to truncated 30s, mono, 44kHz `.wav`, then export to `.safetensors` using Pocket-TTS.

- Bash only (not Windows compatible)
- Requires `ffmpeg` and Python package `uv`
- Usage:
  ```bash
  ./export-voices.sh <input_file_or_directory> <output_directory>
  ```
  Example:
  ```bash
  ./export-voices.sh ./samples ./voices
  ```

See [Pocket-TTS documentation](https://github.com/kyutai-labs/pocket-tts) for full training details.

## Dependency & Environment Setup (Summarized)

- Python 3.x required
- Install dependencies using `uv`:
  ```bash
  uv sync
  ```
- Install ffmpeg (see [ffmpeg download page](https://ffmpeg.org/download.html))
- Create a `voices` directory and add your models
- Place your Discord bot token and config in a `.env` file

## Bot Commands

- `!voice <voice_name>`
  - Set your TTS voice
  - Example: `!voice Joe`
- `!s <text>`
  - Speak text directly (no username prefix)
  - Example: `!s Hello world!`
- `!t <text>`
  - Speak text with your username prefix
  - Example: `!t Testing 1 2 3`
- **Automatic TTS:** Muted user’s text messages are spoken aloud in voice channels.

## Running the Bot

- Setup dependencies
- Add voices to the `voices` directory
- Configure `.env` (Discord bot token, etc.)
- Run the bot with Python

## Links & Resources

- [Pocket-TTS repository](https://github.com/kyutai-labs/pocket-tts)
- [ffmpeg install guides](https://ffmpeg.org/download.html)
- [Discord developer portal](https://discord.com/developers/applications)
- [uv documentation](https://github.com/astral-sh/uv)

## Limitations & Troubleshooting

- `.wav` models are supported but not recommended (slow)
- No command to list voices yet
- Bash script not supported on Windows
- Common issues: missing dependencies, folder structure, Discord bot permissions

## Contributing

Contributions welcome! Please:

- Suggest new features (including Windows-compatible export workflows)
- Submit bug reports and pull requests
- Help extend functionality (such as adding a voice listing command)

Open an issue or PR on GitHub to get involved.
