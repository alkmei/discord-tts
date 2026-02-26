# web/main.py
import os
import uuid
from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from celery import Celery
from dotenv import load_dotenv

load_dotenv()

app = FastAPI()

# --- Configuration ---
REDIS_URL = os.getenv("REDIS_URL")
VOICES_DIR = "/app/voices"
SHARED_DIR = "/app/shared"

celery_app = Celery("tts_worker", broker=REDIS_URL, backend=REDIS_URL)

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


# --- HTML Templates ---

BASE_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TTS WebUI</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://unpkg.com/htmx.org@1.9.6"></script>
    <style>
        body {{ background-color: #f8f9fa; }}
        .main-card {{ max-width: 800px; margin: 50px auto; border-radius: 15px; border: none; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }}
        .htmx-indicator {{ display: none; }}
        .htmx-request .htmx-indicator {{ display: block; }}
        .htmx-request.btn-primary {{ display: none; }}
    </style>
</head>
<body>
    <div class="container">
        <div class="card main-card">
            <div class="card-header bg-primary text-white text-center py-3">
                <h2 class="mb-0">Pocket TTS Generator</h2>
            </div>
            <div class="card-body p-4">
                {content}
            </div>
        </div>
    </div>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    voices = get_available_voices()
    options = "".join([f'<option value="{v}">{v}</option>' for v in voices])

    content = f"""
    <form hx-post="/generate" hx-target="#result-area" hx-indicator="#spinner">
        <div class="mb-3">
            <label class="form-label fw-bold">Select Voice</label>
            <select name="voice" class="form-select form-select-lg">{options}</select>
        </div>
        <div class="mb-3">
            <label class="form-label fw-bold">Text to Synthesize</label>
            <textarea name="text" class="form-control" rows="8" placeholder="Paste your long text here..."></textarea>
        </div>
        <div class="d-grid">
            <button type="submit" class="btn btn-primary btn-lg" id="submit-btn">
                Generate Audio
            </button>
            <div id="spinner" class="htmx-indicator text-center mt-3">
                <div class="spinner-border text-primary" role="status"></div>
                <p class="mt-2 text-muted">Sending to Worker...</p>
            </div>
        </div>
    </form>
    
    <div id="result-area" class="mt-4">
        <!-- Result or status updates will appear here via HTMX -->
    </div>
    """
    return BASE_HTML.format(content=content)


@app.post("/generate", response_class=HTMLResponse)
async def generate(text: str = Form(...), voice: str = Form(...)):
    task_id = str(uuid.uuid4())
    filename = f"web_{task_id}.wav"

    # Dispatch to Celery
    celery_app.send_task(
        "worker.tasks.generate_tts_task", args=[text, voice, filename], task_id=task_id
    )

    # Return the "Status Poller" component
    return f"""
    <div class="alert alert-info d-flex align-items-center" 
         hx-get="/status/{task_id}/{filename}" 
         hx-trigger="every 1s" 
         hx-swap="outerHTML">
        <div class="spinner-border spinner-border-sm me-3" role="status"></div>
        <span>Generating audio file... Task ID: <code>{task_id[:8]}</code></span>
    </div>
    """


@app.get("/status/{task_id}/{filename}", response_class=HTMLResponse)
async def status(task_id: str, filename: str):
    res = celery_app.AsyncResult(task_id)

    if res.ready():
        if res.state == "SUCCESS":
            return f"""
            <div class="card border-success">
                <div class="card-body text-center">
                    <h5 class="text-success mb-3">Generation Complete!</h5>
                    <audio controls class="w-100 mb-3 shadow-sm">
                        <source src="/static/audio/{filename}" type="audio/wav">
                        Your browser does not support the audio element.
                    </audio>
                    <div class="d-flex justify-content-center gap-2">
                        <a href="/static/audio/{filename}" download class="btn btn-outline-success btn-sm">Download WAV</a>
                        <button onclick="window.location.reload()" class="btn btn-outline-secondary btn-sm">Clear</button>
                    </div>
                </div>
            </div>
            """
        else:
            return f"""
            <div class="alert alert-danger">
                <strong>Error:</strong> Generation failed. <br>
                <button onclick="window.location.reload()" class="btn btn-sm btn-danger mt-2">Try Again</button>
            </div>
            """

    # If not ready, return the same polling div to keep the loop going
    return f"""
    <div class="alert alert-info d-flex align-items-center" 
         hx-get="/status/{task_id}/{filename}" 
         hx-trigger="every 1s" 
         hx-swap="outerHTML">
        <div class="spinner-border spinner-border-sm me-3" role="status"></div>
        <span>Worker is processing text...</span>
    </div>
    """
