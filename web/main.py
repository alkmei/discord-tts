"""FastAPI web UI for TTS generation."""

from __future__ import annotations

import json
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import aio_pika
from celery import Celery
from dotenv import load_dotenv
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

load_dotenv()

import os

# --- Config ---
RABBITMQ_URL: str = os.getenv("RABBITMQ_URL", "")
celery_app: Celery = Celery("tts_worker", broker=RABBITMQ_URL, backend="rpc://")

SHARED_DIR: Path = Path("/app/shared")
VOICES_DIR: Path = Path("/app/voices")


# RabbitMQ connection state
class RabbitMQState:
    """Container for RabbitMQ connection state."""

    connection: aio_pika.abc.AbstractRobustConnection | None = None
    channel: aio_pika.abc.AbstractChannel | None = None
    exchange: aio_pika.abc.AbstractExchange | None = None


rabbitmq_state: RabbitMQState = RabbitMQState()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialize and cleanup RabbitMQ connection."""
    # Startup
    rabbitmq_state.connection = await aio_pika.connect_robust(RABBITMQ_URL)
    rabbitmq_state.channel = await rabbitmq_state.connection.channel()
    rabbitmq_state.exchange = await rabbitmq_state.channel.declare_exchange(
        "web_tts_requests", aio_pika.ExchangeType.FANOUT, durable=True
    )
    yield
    # Shutdown
    if rabbitmq_state.connection:
        await rabbitmq_state.connection.close()


app: FastAPI = FastAPI(lifespan=lifespan)
templates: Jinja2Templates = Jinja2Templates(directory="web/templates")

app.mount("/static/audio", StaticFiles(directory=str(SHARED_DIR)), name="audio")


def get_available_voices() -> list[str]:
    """Returns sorted list of available voice names."""
    voices: list[str] = []
    if VOICES_DIR.exists():
        for filepath in VOICES_DIR.iterdir():
            ext: str = filepath.suffix
            name: str = filepath.stem
            if ext in [".safetensors", ".wav"]:
                voices.append(name.lower())
    return sorted(voices)


class ParsedLine:
    """Represents a parsed line of TTS text."""

    line_num: int
    voice: str
    text: str
    warnings: list[str]
    filename: str | None = None

    def __init__(self, line_num: int, voice: str, text: str, warnings: list[str]) -> None:
        self.line_num = line_num
        self.voice = voice
        self.text = text
        self.warnings = warnings
        self.filename = None

    def to_dict(self) -> dict[str, int | str | list[str] | None]:
        """Convert to dictionary for template rendering."""
        return {
            "line_num": self.line_num,
            "voice": self.voice,
            "text": self.text,
            "warnings": self.warnings,
            "filename": self.filename,
        }


@app.get("/")
async def index(request: Request) -> HTMLResponse:
    """Render the main index page."""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/voices")
async def voices() -> list[str]:
    """Return list of available voices."""
    return get_available_voices()


def parse_multiline_tts(text: str) -> list[ParsedLine]:
    """Parse multiline TTS text with voice prefixes."""
    available_voices: list[str] = get_available_voices()
    lines: list[str] = text.splitlines()
    parsed: list[ParsedLine] = []
    current_voice: str = "alba"

    for idx, raw_line in enumerate(lines, 1):
        stripped_line: str = raw_line.strip()
        if not stripped_line:
            continue

        warnings: list[str] = []
        chosen_voice: str = current_voice
        message_text: str = stripped_line

        if ":" in stripped_line:
            potential_voice, rest = stripped_line.split(":", 1)
            potential_voice = potential_voice.strip().lower()
            if potential_voice in available_voices:
                chosen_voice = potential_voice
                message_text = rest.strip()
                current_voice = chosen_voice
            else:
                warnings.append(f"Voice '{potential_voice}' not found - using '{current_voice}'")
        else:
            warnings.append(f"Using inherited voice '{current_voice}'")

        parsed.append(
            ParsedLine(
                line_num=idx,
                voice=chosen_voice,
                text=message_text,
                warnings=warnings,
            )
        )
    return parsed


@app.post("/generate")
async def generate(
    request: Request,
    text: Annotated[str, Form()],
    guild_id: Annotated[str | None, Form()] = None,
) -> HTMLResponse:
    """Generate TTS for the given text."""
    if not text.strip():
        return HTMLResponse('<div class="alert alert-warning">Text is empty.</div>')

    parsed_lines: list[ParsedLine] = parse_multiline_tts(text)

    for line_data in parsed_lines:
        task_id: str = str(uuid.uuid4())
        filename: str = f"web_{task_id}.wav"

        line_data.filename = filename

        celery_app.send_task(
            "worker.tasks.generate_tts_task",
            args=[line_data.text, line_data.voice, filename],
            task_id=task_id,
        )

        if guild_id and guild_id.strip().isdigit() and rabbitmq_state.exchange:
            payload: dict[str, int | str] = {
                "guild_id": int(guild_id),
                "task_id": task_id,
                "voice_name": line_data.voice,
                "text": line_data.text[:100],
                "user_name": "Web User",
            }
            # Publish to RabbitMQ exchange
            await rabbitmq_state.exchange.publish(aio_pika.Message(body=json.dumps(payload).encode()), routing_key="")

    # Convert ParsedLine objects to dicts for template
    parsed_dicts: list[dict[str, int | str | list[str] | None]] = [line.to_dict() for line in parsed_lines]

    return templates.TemplateResponse(
        "partials/result.html",
        {"request": request, "parsed_lines": parsed_dicts, "guild_id": guild_id},
    )
