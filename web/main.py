# web/main.py
import os
import uuid
import json
import redis
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()
REDIS_URL = os.getenv("REDIS_URL")
r_client = redis.from_url(REDIS_URL)
celery_app = Celery("tts_worker", broker=REDIS_URL, backend=REDIS_URL)

VOICES_DIR = "/app/voices"
SHARED_DIR = "/app/shared"

if not os.path.exists(SHARED_DIR):
    os.makedirs(SHARED_DIR)
app.mount("/static/audio", StaticFiles(directory=SHARED_DIR), name="audio")


def get_available_voices():
    voices = []
    if os.path.exists(VOICES_DIR):
        for filename in os.listdir(VOICES_DIR):
            name, ext = os.path.splitext(filename)
            if ext in [".safetensors", ".wav"]:
                voices.append(name.lower())
    return sorted(voices)


BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>TTS Web Control</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://unpkg.com/htmx.org@1.9.6"></script>
    <style>
        body {{ background-color: #121212; color: #e0e0e0; }}
        .main-card {{ max-width: 900px; margin: 40px auto; background: #1e1e1e; border: 1px solid #333; border-radius: 12px; }}
        .form-control, .form-select {{ background-color: #2b2b2b; border: 1px solid #444; color: #fff; }}
        .form-control:focus, .form-select:focus {{ background-color: #333; color: #fff; border-color: #0d6efd; box-shadow: none; }}
        .alert-info {{ background-color: #0c5460; border: none; color: #bee5eb; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card main-card shadow-lg">
            <div class="card-header border-secondary py-3">
                <h3 class="mb-0">Broadcast to Discord</h3>
            </div>
            <div class="card-body p-4">
                <form hx-post="/generate" hx-target="#result-area" hx-indicator="#spinner">
                    <div class="row g-3 mb-4">
                        <div class="col-md-6">
                            <label class="form-label fw-bold text-primary">Discord Server (Guild) ID</label>
                            <input type="text" name="guild_id" class="form-control form-control-lg" placeholder="Required for Discord playback">
                            <div class="form-text text-muted small">Right-click server icon > Copy ID</div>
                        </div>
                        <div class="col-md-6">
                            <label class="form-label fw-bold text-primary">Your Name</label>
                            <input type="text" name="user_name" class="form-control form-control-lg" placeholder="Web User" value="Web User">
                        </div>
                    </div>

                    <div class="mb-4">
                        <label class="form-label fw-bold">Select Voice</label>
                        <select name="voice" class="form-select form-select-lg">
                            {"".join([f'<option value="{v}">{v}</option>' for v in get_available_voices()])}
                        </select>
                    </div>

                    <div class="mb-4">
                        <label class="form-label fw-bold">Long Text Input</label>
                        <textarea name="text" class="form-control" rows="10" placeholder="Enter chunks of text..."></textarea>
                    </div>

                    <div class="d-grid">
                        <button type="submit" class="btn btn-primary btn-lg py-3 fw-bold">
                            SEND TO DISCORD VOICE
                        </button>
                    </div>

                    <div id="spinner" class="htmx-indicator text-center mt-3">
                        <div class="spinner-border text-primary" role="status"></div>
                        <span class="ms-2">Processing...</span>
                    </div>
                </form>

                <div id="result-area" class="mt-4"></div>
            </div>
        </div>
    </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    return BASE_HTML


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    text: str = Form(...),
    voice: str = Form(...),
    guild_id: str = Form(...),
    user_name: str = Form(...),
):
    if not text.strip():
        return '<div class="alert alert-warning">Please enter some text.</div>'

    task_id = str(uuid.uuid4())
    filename = f"web_{task_id}.wav"

    # 1. Dispatch work to Celery
    celery_app.send_task(
        "worker.tasks.generate_tts_task", args=[text, voice, filename], task_id=task_id
    )

    # 2. Notify Discord Bot via Redis
    if guild_id.strip().isdigit():
        payload = {
            "guild_id": int(guild_id),
            "task_id": task_id,
            "voice_name": voice,
            "text": text[:100] + "..." if len(text) > 100 else text,
            "user_name": user_name,
        }
        r_client.publish("web_tts_requests", json.dumps(payload))
        status_msg = f"Broadcasting to Server {guild_id}..."
    else:
        status_msg = "Generating web preview (No valid Guild ID provided)..."

    return f"""
    <div class="alert alert-info d-flex align-items-center" 
         hx-get="/status/{task_id}/{filename}" hx-trigger="every 1s" hx-swap="outerHTML">
        <div class="spinner-border spinner-border-sm me-3"></div>
        <span>{status_msg}</span>
    </div>
    """


@app.get("/status/{task_id}/{filename}", response_class=HTMLResponse)
async def status(task_id: str, filename: str):
    res = celery_app.AsyncResult(task_id)
    if res.ready():
        return f"""
        <div class="card border-success bg-dark text-white shadow-sm">
            <div class="card-body text-center">
                <h6 class="text-success mb-3">✅ Generation Complete</h6>
                <audio controls class="w-100 mb-2"><source src="/static/audio/{filename}" type="audio/wav"></audio>
                <p class="small text-muted mb-0">The Discord bot is now playing this file.</p>
            </div>
        </div>
        """
    return f"""
    <div class="alert alert-info d-flex align-items-center" 
         hx-get="/status/{task_id}/{filename}" hx-trigger="every 1s" hx-swap="outerHTML">
        <div class="spinner-border spinner-border-sm me-3"></div>
        <span>Worker is synthesizing audio...</span>
    </div>
    """
