# SmartClass AI — Web-Based Teaching & Classroom Analytics Platform

**Course:** Introduction to Software Engineering (Ex2 — OOP / OOD)  
**Institution:** Ariel University  
**Authors:** Ron Perelman (212418735) & Shlomo Tousieh Cohen (331294710)

---

## 1. Problem Statement

Traditional classroom management and engagement tools introduce high friction and fail to verify real participation:
- **Time-Consuming & Easily Gamed Attendance:** Manual roll-calls waste 5–15 minutes per lecture, while single-action sign-in sheets or static QR codes allow students to register attendance and leave immediately.
- **Passive Lecture Experience:** Lecturers lack frictionless, zero-setup ways to run quick comprehension checks and live in-class quizzes without forcing students to install native mobile apps or create complex accounts.
- **Unstandardized Post-Lecture Workflows:** Producing structured summaries from Zoom/Google Meet recordings and delivering consistent, comparative Object-Oriented Design (OOD/SOLID) feedback across student homework repositories is tedious and slow.

**SmartClass AI** solves these issues using the **KISS (Keep It Simple, Stupid)** principle: a single-server FastAPI + SQLite web suite pairing computer-vision dwell-time attendance tracking, 5-minute time-gated QR interaction, real-time WebSocket polling/Q&A, and AI-assisted lecture summarization and homework evaluation.

---

## 2. Scope of the Project

### In Scope
- **Localhost / Containerized Web Server:** Self-contained FastAPI backend (`uvicorn` single-worker) with SQLite persistence (`smartclass.db`) and a zero-build static frontend (`/static`) using Tailwind CSS, Vanilla ES6 JavaScript, Axios, `QRCode.js`, and `Chart.js`.
- **Role-Based Local Access:** Student login/profile persistence via ID (`ת.ז`) and Lecturer authentication via ID + password.
- **5 Integrated Teaching Features:**
  1. **Automated Visual Attendance & Export:** Classroom frame/webcam/video ingestion using **YOLOv8n + ByteTrack** (with automatic fallback mock tracker when CV dependencies are absent), configurable `PresencePolicy` (`PercentagePresencePolicy` at 70% threshold or `FixedTimePresencePolicy`), and Pandas CSV export.
  2. **5-Minute Timed QR Quizzes:** `.xlsx` question bank upload (`openpyxl`), exhausted-bank alerts, 300-second expiring QR tokens (`/s/{token}`), HTTP `403`/`410` rejection after expiry, and dual-factor correlation with active attendance records.
  3. **Instant KISS Live Polls & Class Q&A / Blog:** 1-click 2–4 option polls with real-time `Chart.js` telemetry, shared chronological class Q&A feed (`/forum`), and private student-to-lecturer messaging.
  4. **AI Lecture Recording Summarizer:** `.mp4` / `.m4a` / `.txt` upload with progress tracking, LLM/fallback structured Markdown generation (Main Concepts, Time-Indexed Topics, Follow-Up Discussion), `SUMMARY_READY` WebSocket push, and automatic publishing to the Class Forum.
  5. **AI Homework Comparative Review:** Evaluates submitted student repository URLs for SOLID/OOD quality, cohesion, and coupling, producing individual rubric scores and cross-student comparative anti-pattern notes.

### Out of Scope
- Direct integration with external university SSO systems (Moodle / מידע אישי).
- Live Zoom/Google Meet cloud webhook streaming (recordings are uploaded post-lecture).
- Native iOS/Android app distribution (students interact exclusively through mobile web browsers).

---

## 3. Tech Stack

| Layer | Technology |
| :--- | :--- |
| **Backend** | Python 3.10, FastAPI, Uvicorn (single-worker), WebSockets |
| **Database** | SQLite (WAL mode) + SQLAlchemy 2.0 ORM |
| **Computer Vision & Data** | YOLOv8n (`ultralytics`), OpenCV Headless, ByteTrack, Pandas, OpenPyXL |
| **AI / LLM** | OpenAI API (`OPENAI_API_KEY`, with deterministic offline fallback) |
| **Frontend** | Pure HTML5, Tailwind CSS (CDN), Vanilla ES6 JS, Axios, QRCode.js, Chart.js |
| **Deployment** | Docker & Docker Compose (`python:3.10-slim` + CPU-only PyTorch) |

---

## 4. Running with Docker (Recommended)

### Prerequisites
- [Docker](https://docs.docker.com/get-docker/) and [Docker Compose](https://docs.docker.com/compose/)

### Setup & Launch
1. Copy the example environment file and optionally add your OpenAI API key:
   ```bash
   cp .env.example .env
   ```
2. Build and start the container:
   ```bash
   docker compose up --build -d
   ```
3. Access the application in your browser:
   - **Lecturer Dashboard:** `http://localhost:8000/`
   - **Student Mobile View:** `http://localhost:8000/live` (or scan the projected QR `/s/{token}`)
   - **Class Q&A / Forum:** `http://localhost:8000/forum`
   - **Interactive OpenAPI Docs:** `http://localhost:8000/docs`

### Persistent Volumes & Deployment Notes
- `./data` -> `/app/data` (SQLite database `smartclass.db`)
- `./uploads` -> `/app/uploads` (uploaded `.xlsx` question banks, recordings, and classroom frames)
- `./reports` -> `/app/reports` (exported CSV attendance reports)
- **Single-Worker Requirement:** The container runs Uvicorn with 1 worker (`--port 8000`) to preserve in-memory `ByteTrack` trajectories and active WebSocket connections.
- **Cloud Webcam Support:** When hosted in the cloud without a physical USB camera, use the dashboard's **Start Webcam Stream** (browser Canvas frames) or **Upload Frame / Video** button.

---

## 5. Local Development (Without Docker)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
