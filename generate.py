import os

import scipy.io.wavfile
from pocket_tts import TTSModel

# --- Configuration ---
INPUT_SCRIPT = "script.txt"
VOICES_DIR = "./voices"
OUTPUT_DIR = "./output"

# Initialize Model (Singleton style)
print("⏳ Loading Pocket TTS Model...")
model = TTSModel.load_model()
print(f"✅ Model loaded on {model.device}")

# Simple LRU-style cache for voice states to speed up multi-line scripts
voice_state_cache = {}


def get_voice_map():
    """
    Scans the ./voices folder and creates a mapping of
    filename (without extension) -> full path.
    """
    mapping = {}
    if not os.path.exists(VOICES_DIR):
        print(f"⚠️ Warning: Folder '{VOICES_DIR}' not found.")
        return mapping

    for file in os.listdir(VOICES_DIR):
        if file.endswith(".safetensors"):
            voice_name = os.path.splitext(file)[0]
            mapping[voice_name] = os.path.join(VOICES_DIR, file)

    return mapping


def get_cached_voice_state(voice_name, voice_map):
    """Loads and caches the voice state to avoid redundant disk reads."""
    if voice_name in voice_state_cache:
        return voice_state_cache[voice_name]

    if voice_name in voice_map:
        path = voice_map[voice_name]
        print(f"📂 Loading voice state: {voice_name}")
        state = model.get_state_for_audio_prompt(path)
        voice_state_cache[voice_name] = state
        return state

    return None


def process_script():
    # 1. Prepare Environment
    voice_map = get_voice_map()
    if not os.path.exists(OUTPUT_DIR):
        os.makedirs(OUTPUT_DIR)

    if not os.path.exists(INPUT_SCRIPT):
        print(f"❌ Error: Script file '{INPUT_SCRIPT}' not found.")
        return

    # 2. Read and Parse Script
    with open(INPUT_SCRIPT, encoding="utf-8") as f:
        lines = [line.strip() for line in f if line.strip()]

    print(f"📖 Processing {len(lines)} lines...")

    for i, line in enumerate(lines):
        if ":" not in line:
            print(f"⏩ Skipping line {i}: No colon separator found.")
            continue

        voice_name, text = line.split(":", 1)
        voice_name = voice_name.strip()
        text = text.strip()
        text = "." + text  # Prepend period for better prosody

        # 3. Get Voice State
        voice_state = get_cached_voice_state(voice_name, voice_map)

        if voice_state is None:
            print(
                f"❌ Skipping line {i}: Voice '{voice_name}' not found in {VOICES_DIR}"
            )
            continue

        # 4. Generate and Save
        print(f"🎙️ Generating [{voice_name}]: {text[:40]}...")
        try:
            audio_tensor = model.generate_audio(voice_state, text)

            # Create filename (e.g., 001_Sarah.wav)
            filename = f"{i:03d}_{voice_name}.wav"
            output_path = os.path.join(OUTPUT_DIR, filename)

            # Convert to CPU numpy for scipy saving
            audio_data = audio_tensor.cpu().numpy()
            scipy.io.wavfile.write(output_path, model.sample_rate, audio_data)
        except Exception as e:
            print(f"🔥 Error on line {i}: {e}")

    print(f"✨ Done! Audio files are in '{OUTPUT_DIR}'")


if __name__ == "__main__":
    process_script()
