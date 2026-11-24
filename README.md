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
  3. **Instant KISS Live Polls & Course Forum:** 1-click 2–4 option polls with real-time `Chart.js` telemetry, a per-course discussion forum (`/forum`) with threads and replies over plain REST, and private student-to-lecturer messaging.
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
   - **Login (Students & Lecturers):** `http://localhost:8000/`
   - **Lecturer Dashboard:** `http://localhost:8000/lecturer_dashboard`
   - **Student Mobile View:** `http://localhost:8000/student_dashboard` (or scan the projected QR `/s/{token}`)
   - **Course Forum:** `http://localhost:8000/forum`
   - **Interactive OpenAPI Docs:** `http://localhost:8000/docs`

### Persistent Volumes & Deployment Notes
- `./data` -> `/app/data` (SQLite database `smartclass.db`)
- `./uploads` -> `/app/uploads` (uploaded `.xlsx` question banks, recordings, and classroom frames)
- `./reports` -> `/app/reports` (exported CSV attendance reports)
- **Single-Worker Requirement:** The container runs Uvicorn with 1 worker (`--port 8000`) to preserve in-memory `ByteTrack` trajectories and active WebSocket connections.
- **Cloud Webcam Support:** When hosted in the cloud without a physical USB camera, use the dashboard's **Start Webcam Stream** (browser Canvas frames) or **Upload Frame / Video** button.

---

## 5. Local Development (Without Docker)

Requires **Python 3.10+**. Run all commands from the project root (the folder containing `app/`).

```bash
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# Windows (cmd):        .venv\Scripts\activate.bat
# macOS/Linux:          source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

Then open `http://localhost:8000/`. On first start the app creates `data/smartclass.db`, seeds three sample courses and the default lecturer (see below).

> Using `python -m uvicorn` (rather than plain `uvicorn`) makes sure the server runs with the virtual environment's Python and finds the `app` package.

### Running the Tests

```bash
python -m pytest -q
```

---

## 6. Accounts & Default Lecturer

- **Students** log in with their ID only. A profile is created automatically on first login.
- **Lecturers** log in with ID + password. A new lecturer account is created the first time an unused ID logs in with a password.
- On startup, a **default lecturer** is created (if that ID is not taken yet) and assigned to the three sample courses that have no lecturer:

  | Variable | Default |
  | :--- | :--- |
  | `DEFAULT_LECTURER_ID` | `111111111` |
  | `DEFAULT_LECTURER_NAME` | `Default Lecturer` |
  | `DEFAULT_LECTURER_PASSWORD` | `admin123` |

  To change it, edit these values in `docker-compose.yml` (Docker) or set them as environment variables / in `.env` (local). **Change the password before deploying anywhere public.**
- Notes on replacing the default lecturer:
  - The password is only used when the account is **first created**. Changing it later does not update an existing account.
  - A new `DEFAULT_LECTURER_ID` creates a new lecturer, but courses already assigned to the old one stay with them. Move them with:
    ```http
    PATCH /api/courses/{course_id}/lecturer
    { "acting_lecturer_id": "<your lecturer ID>", "lecturer_id": "<new lecturer ID>" }
    ```
    The new lecturer must have logged in at least once.

### Other Environment Variables

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DATABASE_URL` | `data/smartclass.db` in the project folder | SQLite database location (SQLAlchemy URL, e.g. `sqlite:///./data/smartclass.db`) |
| `SECRET_KEY` | `supersecret_kiss_key` | Salt for lecturer password hashes. Changing it invalidates existing lecturer passwords. |
| `OPENAI_API_KEY` | *(empty)* | Enables real LLM summaries/reviews; without it a deterministic offline fallback is used |

---

## 7. Course Forum

- `/forum` shows a tab for each course the user **teaches** (lecturers) or is **approved for** (students). Pending enrollments do not appear.
- Each course has its own threads (title + message) with replies underneath.
- It uses plain REST calls (no WebSockets): new posts from other users appear after switching course or reloading the page.
- Endpoints (the server checks access on every call):
  - `GET  /api/courses/{course_id}/posts?user_id=…`: threads with nested replies
  - `POST /api/courses/{course_id}/posts`: `{ author_id, title, content }`
  - `POST /api/posts/{post_id}/comments`: `{ author_id, content }`
- AI lecture summaries and private messages still use the older `/api/forum/posts` feed and are **not** shown in the course forum.

---

## 8. Troubleshooting

- **`ModuleNotFoundError: No module named 'app'`:** run the command from the project root, and use `python -m uvicorn ...`.
- **`uvicorn: command not found` / wrong packages:** the virtual environment isn't active. Activate it, or call `.venv\Scripts\python -m uvicorn ...` directly.
- **PowerShell refuses to run `Activate.ps1`:** run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- **Start over with a clean database:** stop the server and delete `data/smartclass.db` (plus `-wal` / `-shm` files). It is recreated and re-seeded on the next start.
