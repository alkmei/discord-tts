import argparse
import shutil
import subprocess
from pathlib import Path

# Supported audio extensions
SUPPORTED_EXTENSIONS = {".wav", ".mp3", ".flac", ".m4a", ".ogg", ".opus"}


def check_dependencies():
    """Ensure ffmpeg and uv are installed."""
    if not shutil.which("ffmpeg"):
        print("Error: ffmpeg is not installed or not in your PATH.")
        exit(1)
    if not shutil.which("uv"):
        print("Error: 'uv' is not installed. Please install it to run pocket-tts.")
        exit(1)


def process_file(input_file, output_dir, temp_dir):
    """Processes a single audio file: Truncates with FFmpeg, then exports via pocket-tts."""
    input_path = Path(input_file)

    # Validate extension
    if input_path.suffix.lower() not in SUPPORTED_EXTENSIONS:
        return False

    filename_no_ext = input_path.stem
    output_path = Path(output_dir) / f"{filename_no_ext}.safetensors"
    temp_audio = Path(temp_dir) / f"{filename_no_ext}_30s.wav"

    print("-" * 51)
    print(f"Processing: {input_path.name}")

    try:
        # 1. Truncate to 30s using ffmpeg
        # -ar 44100: Set audio rate, -ac 1: Set to mono
        subprocess.run(
            [
                "ffmpeg",
                "-y",
                "-i",
                str(input_path),
                "-t",
                "30",
                "-ar",
                "44100",
                "-ac",
                "1",
                str(temp_audio),
                "-loglevel",
                "error",
            ],
            check=True,
        )

        # 2. Export voice using pocket-tts via uv
        subprocess.run(
            [
                "uv",
                "run",
                "pocket-tts",
                "export-voice",
                str(temp_audio),
                str(output_path),
            ],
            check=True,
        )

        print(f"Success: {output_path}")

    except subprocess.CalledProcessError as e:
        print(f"Error processing {input_path.name}: {e}")
    finally:
        # 3. Clean up the temp file if it exists
        if temp_audio.exists():
            temp_audio.unlink()


def main():
    parser = argparse.ArgumentParser(
        description="Convert audio files to pocket-tts safetensors."
    )
    parser.add_argument("input", help="Input file or directory")
    parser.add_argument("output_dir", help="Directory to save .safetensors files")
    args = parser.parse_args()

    input_path = Path(args.input)
    output_dir = Path(args.output_dir)
    temp_dir = Path("./temp_processing")

    check_dependencies()

    # Create directories
    output_dir.mkdir(parents=True, exist_ok=True)
    temp_dir.mkdir(parents=True, exist_ok=True)

    if input_path.is_file():
        process_file(input_path, output_dir, temp_dir)
    elif input_path.is_dir():
        print(f"Scanning directory: {input_path}")
        for file in input_path.iterdir():
            if file.is_file():
                process_file(file, output_dir, temp_dir)
    else:
        print(f"Error: '{args.input}' is not a valid file or directory.")
        exit(1)

    # Clean up temp folder if empty
    try:
        if temp_dir.exists() and not any(temp_dir.iterdir()):
            temp_dir.rmdir()
    except OSError:
        pass

    print("-" * 51)
    print("Done.")


if __name__ == "__main__":
    main()
