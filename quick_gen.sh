#!/bin/bash

# Check if correct number of arguments are provided
if [ "$#" -ne 2 ]; then
    echo "Usage: $0 \"Your text here\" \"voice_name\""
    echo "Example: $0 \"Hello world\" \"en_alice\""
    exit 1
fi

TEXT=$1
VOICE_NAME=$2

# 1. Generate the slug from the text
# - Convert to lowercase
# - Replace non-alphanumeric characters with hyphens
# - Remove duplicate hyphens
# - Trim hyphens from start and end
# - Limit to 50 characters for filename safety
SLUG=$(echo "$TEXT" | \
    tr '[:upper:]' '[:lower:]' | \
    sed 's/[^a-z0-9]/-/g' | \
    sed 's/-\{2,\}/-/g' | \
    sed 's/^-//;s/-$//' | \
    cut -c 1-50)

# If slug became empty (e.g. text was just symbols), use a timestamp
if [ -z "$SLUG" ]; then
    SLUG="output-$(date +%s)"
fi

# 2. Define Paths
VOICE_PATH="./voices/${VOICE_NAME}.safetensors"
OUTPUT_DIR="./output"
OUTPUT_PATH="${OUTPUT_DIR}/${SLUG}.wav"

# 3. Ensure output directory exists
mkdir -p "$OUTPUT_DIR"

# 4. Check if voice file exists
if [ ! -f "$VOICE_PATH" ]; then
    echo "Error: Voice file not found at $VOICE_PATH"
    exit 1
fi

# 5. Run the command
echo "Generating: $OUTPUT_PATH"
uv run pocket-tts --text "$TEXT" --voice "$VOICE_PATH" --output-path "$OUTPUT_PATH"