# Technical Tools Evaluation Report

This report evaluates the tools and libraries selected for **SmartClass AI**, compares them against alternatives, and records practical verification results.

---

## 1. Selected Tools & Practical Validation

| Tool / Library | Purpose | Alternatives Considered | Why Chosen | Tested in Real Life |
| :--- | :--- | :--- | :--- | :--- |
| **Ultralytics YOLOv8n** | Person detection (`classes=[0]`) in classroom photos, webcam frames, and sampled video | YOLOv5, MediaPipe Pose, Haar Cascades | Fast CPU inference, clean Python API, built-in tracker hooks, pre-cached `yolov8n.pt` in Docker. | Tested in Docker image build (`YOLO('yolov8n.pt')`) and mock-isolated unit tests; **TODO:** record exact person count & latency (ms) on the course sample classroom photo. |
| **ByteTrack** | Multi-object tracking across frames (`track_id`) | DeepSORT, SORT | Associates low-confidence detections without heavy GPU Re-ID embeddings. | Verified frame-to-frame dwell accumulation in `AttendanceManager` tests; **TODO:** measure ID-switch rate on a 2-minute classroom clip. |
| **OpenCV (`opencv-python-headless`)** | Image decoding, video frame sampling (`VideoCapture`), bounding-box drawing | Pillow, FFmpeg-python, MoviePy | Lightweight headless wheel for Linux containers; decodes both images and video streams. | Verified photo bounding-box annotation and video sampling pipeline in `tests/test_phase1_features.py`. |
| **FastAPI + Uvicorn** | Async REST API, WebSockets, OpenAPI `/docs`, static file serving | Flask, Django, Express.js | Native async WebSocket support, Pydantic v2 validation, automatic Swagger UI, zero boilerplate. | Verified across all 92 pytest integration/contract tests (`< 9s` total suite runtime). |
| **SQLite + SQLAlchemy 2.0** | Embedded ACID database (`data/smartclass.db`) with WAL mode | PostgreSQL, MongoDB, JSON files | Zero external DB server needed for 10-minute demo; WAL + `busy_timeout=5000` handles concurrent student bursts. | Verified 20 concurrent quiz submissions via `ThreadPoolExecutor` in `tests/test_api_integration.py` without table locks. |
| **Native WebSockets (`ws_manager.py`)** | Real-time quiz, poll, attendance, forum, and message broadcasts | Socket.IO, SSE, HTTP polling | Built into FastAPI and every modern browser; zero extra JS client bundle. | Verified `QUIZ_UPDATE`, `POLL_UPDATE`, `ATTENDANCE_DONE`, `FORUM_THREAD_NEW`, `FORUM_COMMENT_NEW`, `STUDENT_MESSAGE_NEW` in `pytest`. |
| **Tailwind CSS (Play CDN)** | Responsive desktop/mobile UI styling | React + Vite, Bootstrap, plain CSS | Zero build step (`package.json`-free), rapid iteration, consistent custom coffee/cream theme. | Verified across `login.html`, `lecturer_dashboard.html`, `student_dashboard.html`, `forum.html`. |
| **Chart.js & QRCode.js** | Live poll/quiz bar charts & projector QR codes | D3.js, ApexCharts, server-side `qrcode` | Tiny CDN scripts; client-side QR generation uses `window.location.origin` automatically for LAN IPs. | Verified QR URL generation (`/s/{token}`, `/checkin/{token}`) and chart data updates in browser. |
| **OpenAI GPT-4o-mini & Whisper API** | Lecture transcription/summarization & rubric-based code review | Claude API, local Llama/Mistral | Single SDK (`openai`), structured JSON mode for rubrics, `whisper-1` for audio. | Verified via mocked/offline fallback paths; **TODO:** record live API latency and token cost on a 30-min lecture recording. |
| **faster-whisper + ffmpeg** | Local CPU audio extraction & transcription when no API key is set | OpenAI Whisper PyTorch, Vosk | `ffmpeg` extracts 16 kHz mono WAV; `faster-whisper` (`tiny`/`base` int8) runs on CPU without GPU. | `ffmpeg` is baked into `Dockerfile`; **TODO:** measure CPU transcription time for a 5-minute `.mp4` inside Docker. |
| **pandas + openpyxl** | Excel `.xlsx` quiz bank parsing and `.csv`/`.xlsx` attendance export | Python `csv` module only | Reads lecturer `.xlsx` sheets cleanly and writes both `.csv` and formatted `.xlsx` attendance sheets. | Verified `.xlsx` quiz import and `.csv`/`.xlsx` export column schemas in `pytest`. |
| **Docker & Docker Compose** | Reproducible container packaging (`python:3.11-slim`, CPU PyTorch) | Bare-metal `venv` only | Isolates `libgl1`, `libglib2.0-0`, `ffmpeg`, and pre-cached YOLO weights across Windows/macOS/Linux. | `Dockerfile` and `docker-compose.yml` configured; **TODO:** record final image size (`docker images`) and cold-start time. |

---

## 2. Rejected Alternatives

| Rejected Tool | Why Evaluated | Why Rejected |
| :--- | :--- | :--- |
| **Face Recognition (FaceNet / ArcFace / `dlib`)** | Direct student identification from classroom video | Raises privacy concerns (biometric data), requires pre-registered face photos, and `dlib` C++ compilation bloats Docker builds. Replaced by anonymous ByteTrack + QR self check-in/quiz linking. |
| **React + Vite / Webpack** | Component-based SPA frontend | Adds Node.js toolchain, `node_modules`, and build steps that violate the KISS zero-build constraint. |
| **Socket.IO** | Real-time rooms and auto-reconnect | Requires custom protocol framing and an extra client/server dependency; native WebSocket + 15-line reconnect wrapper suffices. |
| **Firebase / Supabase** | Hosted auth, real-time DB, and storage | Requires external cloud accounts, internet dependency, and breaks offline/LAN-only classroom demo resilience. |
