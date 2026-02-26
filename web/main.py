import os
import uuid
import json
import redis
from fastapi import FastAPI, Form
from fastapi.responses import HTMLResponse, JSONResponse
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
    <title>TTS Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <script src="https://unpkg.com/htmx.org@1.9.6"></script>
    <style>
        body { background-color: #f8f9fa; color: #333; font-family: 'Inter', sans-serif; }
        .navbar { background-color: #ffffff; border-bottom: 1px solid #dee2e6; }
        .card { border: none; border-radius: 12px; box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075); }
        .editor-container { 
            height: 500px; 
            border: 1px solid #ced4da; 
            border-radius: 8px; 
            overflow: hidden;
        }
        #editor { width: 100%; height: 100%; }
        .voice-badge { 
            display: inline-block; 
            padding: 0.25em 0.6em; 
            font-size: 0.75em; 
            font-weight: 700; 
            border-radius: 0.375rem;
            background-color: #e7f1ff;
            color: #0d6efd;
            margin: 2px;
        }
        .instruction-card { background-color: #fff; height: 100%; }
        .htmx-indicator { display: none; }
        .htmx-request .htmx-indicator { display: block; }
        pre { background: #f1f3f5; padding: 1rem; border-radius: 8px; font-size: 0.85rem; }
        .line-preview { font-family: 'SFMono-Regular', Consolas, monospace; font-size: 0.85rem; }
    </style>
</head>
<body>
    <nav class="navbar mb-4">
        <div class="container">
            <span class="navbar-brand mb-0 h1 text-primary">Discord TTS Dashboard</span>
        </div>
    </nav>

    <div class="container">
        <div class="row g-4">
            <!-- Left Column: Instructions -->
            <div class="col-lg-4">
                <div class="card instruction-card p-4">
                    <h5 class="fw-bold mb-3">📘 Instructions</h5>
                    <p class="text-muted small">Control multiple voices in one broadcast by prefixing lines.</p>
                    
                    <div class="mb-3">
                        <label class="small fw-bold text-uppercase text-muted">Format</label>
                        <pre><code>voice_name: your message</code></pre>
                    </div>

                    <div class="mb-3">
                        <label class="small fw-bold text-uppercase text-muted">Example</label>
                        <pre class="mb-0"><code>alba: Hello!
alice: Hi there!
This continues as Alice.</code></pre>
                    </div>

                    <div class="mb-0">
                        <label class="small fw-bold text-uppercase text-muted">Available Voices</label>
                        <div id="available-voices" class="mt-2">
                            <div class="spinner-border spinner-border-sm text-primary" role="status"></div>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Right Column: Form and Editor -->
            <div class="col-lg-8">
                <div class="card p-4">
                    <form hx-post="/generate" hx-target="#result-area" hx-indicator="#spinner">
                        <div class="mb-6">
                            <label class="form-label fw-semibold">Discord Server ID</label>
                            <input type="text" name="guild_id" class="form-control" placeholder="Paste Guild ID here">
                        </div>

                        <div class="mb-4">
                            <label class="form-label fw-semibold">Script Editor</label>
                            <div class="editor-container">
                                <div id="editor"></div>
                            </div>
                            <textarea name="text" id="hidden-text" style="display:none;"></textarea>
                        </div>

                        <div class="d-flex align-items-center justify-content-between">
                            <button type="submit" class="btn btn-primary btn-lg px-5 shadow-sm" onclick="syncEditorContent()">
                                Broadcast to Discord
                            </button>
                            
                            <div id="spinner" class="htmx-indicator">
                                <div class="d-flex align-items-center text-primary">
                                    <div class="spinner-border spinner-border-sm me-2"></div>
                                    <span class="small fw-bold">Processing Script...</span>
                                </div>
                            </div>
                        </div>
                    </form>

                    <div id="result-area" class="mt-4"></div>
                </div>
            </div>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs/loader.js"></script>
    <script>
        let editor;
        let availableVoices = [];

        fetch('/voices')
            .then(r => r.json())
            .then(voices => {
                availableVoices = voices;
                const container = document.getElementById('available-voices');
                container.innerHTML = voices.map(v => `<span class="voice-badge">${v}</span>`).join('');
                initMonaco();
            });

        function initMonaco() {
            require.config({ paths: { vs: 'https://cdn.jsdelivr.net/npm/monaco-editor@0.45.0/min/vs' } });
            require(['vs/editor/editor.main'], function() {
                monaco.languages.register({ id: 'tts-multi' });

                monaco.languages.setMonarchTokensProvider('tts-multi', {
                    voices: availableVoices,
                    tokenizer: {
                        root: [
                            [/^([a-zA-Z_]+)(:)/, {
                                cases: {
                                    '$1@voices': ['voice.valid', 'delimiter'],
                                    '@default': ['voice.invalid', 'delimiter']
                                }
                            }],
                            [/.*$/, 'message']
                        ]
                    }
                });

                monaco.editor.defineTheme('tts-light', {
                    base: 'vs', // SWITCHED TO LIGHT THEME
                    inherit: true,
                    rules: [
                        { token: 'voice.valid', foreground: '0d6efd', fontStyle: 'bold' },
                        { token: 'voice.invalid', foreground: 'dc3545', fontStyle: 'bold' },
                        { token: 'message', foreground: '198754' }
                    ],
                    colors: {
                        'editor.background': '#ffffff',
                    }
                });

                editor = monaco.editor.create(document.getElementById('editor'), {
                    value: 'alba: Hello! Welcome to the new UI.\\nalice: This looks much cleaner.\\nIt even handles multiple lines easily.',
                    language: 'tts-multi',
                    theme: 'tts-light',
                    fontSize: 14,
                    lineNumbers: 'on',
                    minimap: { enabled: false },
                    automaticLayout: true,
                    renderLineHighlight: 'none',
                    scrollBeyondLastLine: false,
                    wordWrap: 'on'
                });
            });
        }

        function syncEditorContent() {
            if (editor) {
                document.getElementById('hidden-text').value = editor.getValue();
            }
        }
    </script>
</body>
</html>
"""


@app.get("/", response_class=HTMLResponse)
async def index():
    # No .format() call needed, no f-string prefix used.
    return BASE_HTML


@app.get("/voices", response_class=JSONResponse)
async def voices():
    return get_available_voices()


def parse_multiline_tts(text: str):
    """
    Parse multi-line TTS input following bot's multi command logic.
    Returns a list of dicts: [{"line_num": int, "voice": str, "text": str, "warnings": [str]}]
    """
    available_voices = get_available_voices()
    lines = text.splitlines()
    parsed = []
    current_voice = "alba"  # Default voice

    for idx, line in enumerate(lines, 1):
        line = line.strip()
        if not line:  # Skip empty lines
            continue

        warnings = []
        chosen_voice = None
        message_text = line

        # Check if line has voice prefix
        if ":" in line:
            potential_voice, rest = line.split(":", 1)
            potential_voice = potential_voice.strip().lower()

            if potential_voice in available_voices:
                # Valid voice prefix
                chosen_voice = potential_voice
                message_text = rest.strip()
                current_voice = chosen_voice
            else:
                # Check if this looks like a voice prefix attempt
                if len(potential_voice) < 20 and potential_voice.isalpha():
                    # Invalid voice prefix - default to alba
                    warnings.append(
                        f"Voice '{potential_voice}' not found - defaulting to alba"
                    )
                    chosen_voice = "alba"
                    message_text = rest.strip()
                    current_voice = "alba"
                else:
                    # Not a voice prefix, just a colon in the message
                    # Use previous voice
                    chosen_voice = current_voice
                    warnings.append(
                        f"No voice prefix - using previous voice '{current_voice}'"
                    )
        else:
            # No prefix - use previous line's voice
            chosen_voice = current_voice
            warnings.append(f"No voice prefix - using previous voice '{current_voice}'")

        parsed.append(
            {
                "line_num": idx,
                "voice": chosen_voice,
                "text": message_text,
                "warnings": warnings,
            }
        )

    return parsed


@app.post("/generate", response_class=HTMLResponse)
async def generate(
    text: str = Form(...),
    guild_id: str = Form(...),
):
    if not text.strip():
        return '<div class="alert alert-warning">Please enter some text.</div>'

    # Parse multi-line input
    parsed_lines = parse_multiline_tts(text)

    if not parsed_lines:
        return '<div class="alert alert-warning">No valid lines to process.</div>'

    # Process each line
    task_ids = []
    for line_data in parsed_lines:
        task_id = str(uuid.uuid4())
        filename = f"web_{task_id}.wav"

        # 1. Dispatch work to Celery
        celery_app.send_task(
            "worker.tasks.generate_tts_task",
            args=[line_data["text"], line_data["voice"], filename],
            task_id=task_id,
        )

        # 2. Notify Discord Bot via Redis
        if guild_id.strip().isdigit():
            payload = {
                "guild_id": int(guild_id),
                "task_id": task_id,
                "voice_name": line_data["voice"],
                "text": line_data["text"][:100] + "..."
                if len(line_data["text"]) > 100
                else line_data["text"],
                "user_name": "Web User",
            }
            r_client.publish("web_tts_requests", json.dumps(payload))

        task_ids.append(task_id)

    # Build preview response
    preview_html = '<div class="card border-info bg-dark text-white shadow-sm mb-3"><div class="card-body">'
    preview_html += f'<h6 class="text-info mb-3">✅ Queued {len(parsed_lines)} line(s) for Discord playback</h6>'
    preview_html += '<table class="table table-dark table-sm">'
    preview_html += '<thead><tr><th style="width:50px">#</th><th style="width:100px">Voice</th><th>Message</th><th style="width:50px">Status</th></tr></thead>'
    preview_html += "<tbody>"

    for line_data in parsed_lines:
        warning_icon = "⚠️" if line_data["warnings"] else ""
        warnings_text = "<br>".join(
            [f'<small class="warning-icon">{w}</small>' for w in line_data["warnings"]]
        )
        text_preview = (
            line_data["text"][:80] + "..."
            if len(line_data["text"]) > 80
            else line_data["text"]
        )

        preview_html += f"""
        <tr>
            <td>{line_data["line_num"]}</td>
            <td><span class="voice-badge">{line_data["voice"]}</span></td>
            <td class="line-preview">{text_preview}{warnings_text and "<br>" + warnings_text or ""}</td>
            <td>{warning_icon}</td>
        </tr>
        """

    preview_html += "</tbody></table>"

    if guild_id.strip().isdigit():
        preview_html += f'<p class="small text-muted mb-0 mt-2">Broadcasting to Discord Server {guild_id}</p>'
    else:
        preview_html += '<p class="small text-warning mb-0 mt-2">⚠️ No valid Guild ID - files generated but not sent to Discord</p>'

    preview_html += "</div></div>"

    return preview_html
