# ==========================================
# Stage 1: Builder
# ==========================================
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim AS builder

# Install build dependencies
# - build-essential/libffi-dev: Required to compile PyNaCl and C extensions
# - git: Required to install pocket-tts from git
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libffi-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

ENV UV_COMPILE_BYTECODE=1

# Copy dependency files first for layer caching
COPY pyproject.toml uv.lock ./

# Install dependencies into the virtual environment
RUN uv sync --frozen --no-install-project --no-dev --no-cache

# ==========================================
# Stage 2: Runtime
# ==========================================
FROM ghcr.io/astral-sh/uv:python3.14-trixie-slim

# Install strict runtime dependencies
# - ffmpeg: Required by discord.py to process/play audio
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy only the compiled virtual environment from the builder
COPY --from=builder /app/.venv /app/.venv

# Copy the application code
COPY . .

COPY scripts/ /app/scripts/
RUN chmod +x /app/scripts/*.sh

# Create directories for media and shared audio files
RUN mkdir -p /app/media /app/shared /app/db

# Set environment variables
ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1

# Default command
CMD ["python", "-m", "bot.main"]