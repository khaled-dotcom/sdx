# AI Action Recognition — README

## Overview
- Web app that analyzes uploaded videos to produce an action recognition report, an executive summary PDF, and optional TTS audio.
- Main components: `web_app.py` (Flask server), `action_recognition.py` (video processing + Groq client), `app/tts.py` (TTS via Groq), `app/pdf_utils.py` (PDF builder), `templates/index.html` (UI).

## Quick start (install + run)
```bash
# change to repo directory
cd "/home/khaledghalwash/Desktop/action recofonation - Copy - Copy (2)(1)/action recofonation - Copy - Copy"

# create and activate virtualenv (recommended)
python -m venv .venv
source .venv/bin/activate

# install dependencies
pip install -r requirements.txt

# set your Groq API key (required)
export GROQ_API_KEY="<your_groq_api_key_here>"

# run the Flask web app
python web_app.py

# open in browser:
# http://127.0.0.1:5000
```

## Required libraries (from `requirements.txt`)
- `groq>=0.4.0`
- `opencv-python>=4.8.0`
- `numpy>=1.24.0`
- `flask>=2.3.0`
- `werkzeug>=2.3.0`
- `fpdf2>=2.7.9`

Recommended Python: Python 3.9+ (3.10/3.11 recommended).

## Environment variables
- `GROQ_API_KEY` — required for model/chat/TTS calls. Set this before running the app.
- `CHAT_API_KEY` — alternative name checked by the code.

**Security note:** The repository contains test API key constants in `web_app.py`. Do NOT use hardcoded keys in production — replace or remove them and always set `GROQ_API_KEY` via environment variables.

## Endpoints (how to use)
- `GET /` — Renders the UI (`templates/index.html`).

- `POST /upload` — Upload a video file (form field `video`). Optional form fields: `frame_interval` (int), `model` (string).
  - Success JSON: `{ success: true, report: <text>, report_file: <filename>, video_file: <filename> }`
  - Example curl:
    ```bash
    curl -F "video=@sample_video.mp4" \
         -F "frame_interval=30" \
         -F "model=meta-llama/llama-4-scout-17b-16e-instruct" \
         http://127.0.0.1:5000/upload
    ```

- `POST /save_recorded_video` — Save a recorded webcam video (field `video`). Returns JSON with `video_file`.

- `GET /report/<filename>` — Download saved `.txt` report.

- `GET /report/pdf/<filename>` — Download a PDF with the executive summary (`app/pdf_utils.build_summary_pdf`).

- `GET /reports/list` — List available `.txt` reports (JSON).

- `POST /chat/report` — Ask questions about a saved report. JSON body: `{ "report_file": "video_report_...txt", "message": "..." }`.

- `POST /chat/project` — Ask about using the project. JSON body: `{ "message": "..." }`.

- `POST /tts` — Convert text -> speech. JSON body: `{ "text": "..." }`. Returns `audio/wav`.

## Files & folders
- `web_app.py` — Flask app and endpoints.
- `action_recognition.py` — `ActionRecognitionSystem` class; frame sampling, Groq-based frame analysis, summary generation.
- `app/tts.py` — `synthesize_speech(text, api_key)` returns WAV bytes via Groq TTS model.
- `app/pdf_utils.py` — `extract_summary_only()` and `build_summary_pdf()` helpers.
- `templates/index.html` — front-end UI.
- `uploads/` — saved uploaded videos.
- `reports/` — saved text reports.

## Usage examples
- CLI processing (direct):
  ```bash
  python action_recognition.py --mode file --video /path/to/video.mp4 --api-key "$GROQ_API_KEY" --interval 30
  ```

- Live webcam analysis:
  ```bash
  python action_recognition.py --mode live --api-key "$GROQ_API_KEY" --interval 30 --duration 20
  ```

## Important configuration values
- Upload folder: `uploads/`
- Reports folder: `reports/`
- Max upload size: `500 MB` (set in `web_app.py` via `app.config['MAX_CONTENT_LENGTH']`).
- Allowed extensions: `mp4, avi, mov, mkv, flv, wmv, webm, m4v`.

## Security & redaction note
- Redaction report: `web_app.py` contains `DEFAULT_API_KEY` and `DEFAULT_CHAT_API_KEY` constants near the top. These are test values in the code and should be removed or replaced.
- Never commit real API keys to source control. Replace with `<REDACTED>` if sharing the code publicly.

## Performance & deployment notes
- Large videos may take long to process due to frame extraction and remote model calls.
  - Increase `frame_interval` to analyze fewer frames.
  - Use asynchronous/background workers (Celery, rq) for long-running jobs.
  - Offload storage to S3 and run workers in containers for scalability.

## Troubleshooting
- If OpenCV fails to open video files: ensure system codecs (ffmpeg/libav) are installed.
- If Groq calls fail: verify `GROQ_API_KEY` and model availability; some models may not support vision or require terms acceptance.
- TTS model `playai-tts` may require terms acceptance in the Groq console — follow error instructions if seen.

## Developer notes
- `action_recognition.py` uses Groq chat completions to analyze frames and to produce the final summary (streaming responses supported).
- `app/pdf_utils.py` uses `fpdf` to build the summary PDF.
- `templates/index.html` contains the front-end UI and JS logic for uploads/status updates.

## Example curl flows
- Upload video:
```bash
curl -X POST -F "video=@sample.mp4" -F "frame_interval=30" http://127.0.0.1:5000/upload
```

- Ask about a report:
```bash
curl -X POST -H "Content-Type: application/json" \
     -d '{"report_file":"video_report_1700000000.txt","message":"Summarize the main actions."}' \
     http://127.0.0.1:5000/chat/report
```

- Get TTS audio:
```bash
curl -s -X POST -H "Content-Type: application/json" \
     -d '{"text":"This is a test audio"}' \
     http://127.0.0.1:5000/tts --output speech.wav
```

## Contributing & next steps
- Add background job queue for long videos.
- Add authentication and restrict report access.
- Add unit/integration tests for `action_recognition.py` and `web_app.py`.
- Add containerization (Dockerfile) and CI for automated testing.

If you want, I can also:
- create a `Dockerfile` and `docker-compose.yml`,
- produce a notebook slide deck describing this project.
