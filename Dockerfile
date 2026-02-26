# Use a Python 3.13 image with uv pre-installed
FROM ghcr.io/astral-sh/uv:python3.13-bookworm-slim

# Install system dependencies
# - ffmpeg: Required by discord.py to play audio
# - build-essential/libffi-dev: Required to compile PyNaCl and other C extensions
# - git: Required to install pocket-tts from the git source
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    build-essential \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Set the working directory
WORKDIR /app

# Enable bytecode compilation for faster startups
ENV UV_COMPILE_BYTECODE=1

# Copy dependency files first for better layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies using uv
# --frozen ensures we use the exact versions in the lockfile
RUN uv sync --frozen --no-install-project --no-dev --no-cache

# Copy the rest of the application code
COPY . .

# Create directories for voices and shared audio files
RUN mkdir -p /app/voices /app/shared

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Default command (can be overridden in docker-compose)
CMD ["python", "bot/main.py"]