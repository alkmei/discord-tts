#!/bin/bash

# Check if correct number of arguments are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 <input_file_or_directory> <output_directory>"
    echo "Example (Dir):  $0 ./samples ./weights"
    echo "Example (File): $0 ./samples/voice.opus ./weights"
    exit 1
fi

INPUT="$1"
OUTPUT_DIR="$2"
TEMP_DIR="./temp_processing"

# Ensure ffmpeg is installed
if ! command -v ffmpeg &> /dev/null; then
    echo "Error: ffmpeg is not installed. Please install it first."
    exit 1
fi

# Create output and temp directories
mkdir -p "$OUTPUT_DIR"
mkdir -p "$TEMP_DIR"

# Function to process a single file
process_file() {
    local file="$1"
    local filename=$(basename -- "$file")
    local extension="${filename##*.}"
    local filename_no_ext="${filename%.*}"

    # Check for supported extensions
    case "${extension,,}" in
        wav|mp3|flac|m4a|ogg|opus)
            local output_path="$OUTPUT_DIR/${filename_no_ext}.safetensors"
            local temp_audio="$TEMP_DIR/${filename_no_ext}_30s.wav"
            
            echo "---------------------------------------------------"
            echo "Processing: $filename"
            
            # 1. Truncate to 30s using ffmpeg
            ffmpeg -y -i "$file" -t 30 -ar 44100 -ac 1 "$temp_audio" -loglevel error
            
            if [ $? -ne 0 ]; then
                echo "Error: FFmpeg failed to process $filename"
                return 1
            fi

            uv run pocket-tts export-voice "$temp_audio" "$output_path"
            
            if [ $? -eq 0 ]; then
                echo "Success: $output_path"
            else
                echo "Error: Pocket-TTS failed on $filename"
            fi

            # 3. Clean up the temp file
            rm "$temp_audio"
            ;;
        *)
            # Ignore non-audio files if in a directory
            if [ -d "$INPUT" ]; then
                return 0
            else
                echo "Error: '$file' does not appear to be a supported audio file."
                return 1
            fi
            ;;
    esac
}

# --- Main Logic ---

if [ -f "$INPUT" ]; then
    # Input is a single file
    process_file "$INPUT"
elif [ -d "$INPUT" ]; then
    # Input is a directory
    echo "Scanning directory: $INPUT"
    for file in "$INPUT"/*; do
        if [ -f "$file" ]; then
            process_file "$file"
        fi
    done
else
    echo "Error: '$INPUT' is not a valid file or directory."
    exit 1
fi

# Clean up temp folder
rmdir "$TEMP_DIR" 2>/dev/null

echo "---------------------------------------------------"
echo "Done."