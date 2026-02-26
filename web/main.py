import os
import uuid
import json
import aio_pika
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
templates = Jinja2Templates(directory="web/templates")

# --- Config ---
RABBITMQ_URL = os.getenv("RABBITMQ_URL")
celery_app = Celery("tts_worker", broker=RABBITMQ_URL, backend="rpc://")

SHARED_DIR = "/app/shared"
VOICES_DIR = "/app/voices"

app.mount("/static/audio", StaticFiles(directory=SHARED_DIR), name="audio")

# RabbitMQ connection and channel will be initialized on startup
rabbitmq_connection = None
rabbitmq_channel = None
rabbitmq_exchange = None


@app.on_event("startup")
async def startup():
    """Initialize RabbitMQ connection on startup."""
    global rabbitmq_connection, rabbitmq_channel, rabbitmq_exchange
    rabbitmq_connection = await aio_pika.connect_robust(RABBITMQ_URL)
    rabbitmq_channel = await rabbitmq_connection.channel()
    rabbitmq_exchange = await rabbitmq_channel.declare_exchange(
        "web_tts_requests", aio_pika.ExchangeType.FANOUT, durable=True
    )


@app.on_event("shutdown")
async def shutdown():
    """Close RabbitMQ connection on shutdown."""
    global rabbitmq_connection
    if rabbitmq_connection:
        await rabbitmq_connection.close()


def get_available_voices():
    voices = []
    if os.path.exists(VOICES_DIR):
        for filename in os.listdir(VOICES_DIR):
            name, ext = os.path.splitext(filename)
            if ext in [".safetensors", ".wav"]:
                voices.append(name.lower())
    return sorted(voices)


@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/voices")
async def voices():
    return get_available_voices()


def parse_multiline_tts(text: str):
    available_voices = get_available_voices()
    lines = text.splitlines()
    parsed = []
    current_voice = "alba"

    for idx, line in enumerate(lines, 1):
        line = line.strip()
        if not line:
            continue

        warnings, chosen_voice, message_text = [], None, line

        if ":" in line:
            potential_voice, rest = line.split(":", 1)
            potential_voice = potential_voice.strip().lower()
            if potential_voice in available_voices:
                chosen_voice = potential_voice
                message_text = rest.strip()
                current_voice = chosen_voice
            else:
                chosen_voice = current_voice
                warnings.append(
                    f"Voice '{potential_voice}' not found - using '{current_voice}'"
                )
        else:
            chosen_voice = current_voice
            warnings.append(f"Using inherited voice '{current_voice}'")

        parsed.append(
            {
                "line_num": idx,
                "voice": chosen_voice,
                "text": message_text,
                "warnings": warnings,
            }
        )
    return parsed


@app.post("/generate")
async def generate(request: Request, text: str = Form(...), guild_id: str = Form(None)):
    if not text.strip():
        return HTMLResponse('<div class="alert alert-warning">Text is empty.</div>')

    parsed_lines = parse_multiline_tts(text)

    for line_data in parsed_lines:
        task_id = str(uuid.uuid4())
        filename = f"web_{task_id}.wav"

        celery_app.send_task(
            "worker.tasks.generate_tts_task",
            args=[line_data["text"], line_data["voice"], filename],
            task_id=task_id,
        )

        if guild_id and guild_id.strip().isdigit():
            payload = {
                "guild_id": int(guild_id),
                "task_id": task_id,
                "voice_name": line_data["voice"],
                "text": line_data["text"][:100],
                "user_name": "Web User",
            }
            # Publish to RabbitMQ exchange
            await rabbitmq_exchange.publish(
                aio_pika.Message(body=json.dumps(payload).encode()), routing_key=""
            )

    return templates.TemplateResponse(
        "partials/result.html",
        {"request": request, "parsed_lines": parsed_lines, "guild_id": guild_id},
    )
