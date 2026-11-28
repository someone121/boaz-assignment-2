# SmartClass AI: Web-Based Teaching & Classroom Analytics Platform

**Course:** Introduction to Software Engineering (Ex2: OOP / OOD)  
**Institution:** Ariel University  
**Authors:** Ron Perelman (212418735) & Shlomo Tousieh Cohen (331294710)

SmartClass AI is a single-server web app for running a lecture:

- attendance from a classroom camera;
- 5-minute QR quizzes;
- live polls;
- a per-course forum;
- AI lecture summaries and homework reviews.

It follows **KISS**: one FastAPI process, one SQLite file, and a static frontend with no build step.

| Documentation | |
| :--- | :--- |
| **This file** | Overview, F1–F5 status, quick start, accounts, configuration |
| [DEMO.md](DEMO.md) | 10-minute in-class demo script & fallback plan |
| [docs/tools-report.md](docs/tools-report.md) | Technical tools evaluation, rejected alternatives, benchmarks |
| [docs/SoW.md](docs/SoW.md) | Statement of Work: objectives, scope, milestones, risks |
| [docs/SRS.md](docs/SRS.md) | IEEE 830 Software Requirements Specification & traceability |
| [docs/use-cases.md](docs/use-cases.md) | User stories, acceptance criteria, use-case diagram |
| [docs/components.md](docs/components.md) | Component diagram & interfaces |
| [docs/class-diagrams.md](docs/class-diagrams.md) | Domain/service/ORM class diagrams & design patterns |
| [docs/sequence-diagrams.md](docs/sequence-diagrams.md) | Sequence diagrams for F1–F5 workflows |
| [docs/testing-strategy.md](docs/testing-strategy.md) | Test levels, component-to-test map, mocking & coverage |
| [docs/backend.md](docs/backend.md) | Architecture, data model, full REST + WebSocket reference |
| [docs/frontend.md](docs/frontend.md) | Pages, JS modules, login state, conventions |
| [docs/docker.md](docs/docker.md) | Image, Compose, volumes, deployment, troubleshooting |
| [docs/conclusion.md](docs/conclusion.md) | Results, limitations, lessons learned, future work |

Assignment documents (requirements and design, written before implementation): [SRS](docs/software_requirements_specification.md), [technical blueprint](docs/technical_system_blueprint.md), [extended spec (Hebrew)](docs/extended_system_specification.md), [original project readme](docs/project_readme.md).

---

## 1. Problem

- **Attendance** by roll-call wastes 5–15 minutes, and sign-in sheets or static QR codes let students sign in and leave.
- **Lectures are passive.** Lecturers lack quick, zero-install ways to check understanding.
- **After the lecture,** writing summaries and giving consistent OOD/SOLID feedback on homework is slow.

## 2. Features (F1–F5) & Status

1. **F1 — Visual Attendance, Self Check-In & Quizzes (Implemented):**
   - Classroom images, webcam frames, and OpenCV-sampled videos (`yolo_video`) go through **YOLOv8n + ByteTrack** (mock only when YOLO cannot load).
   - Single class photo counting (`POST /api/attendance/count-photo`) with bounding boxes.
   - Short-lived student QR self check-in (`/checkin/{token}` → `"I'm Here"`).
   - 5-minute `.xlsx` QR quizzes (`/s/{token}`) with `403`/`410` expiry enforcement.
   - Unified online table + offline `.csv` and `.xlsx` exports.
2. **F2 — Real-Time Course Forum & Private Suggestions (Implemented):**
   - Course-scoped threads and replies broadcast live (`FORUM_THREAD_NEW`, `FORUM_COMMENT_NEW`).
   - Private student messages/suggestions stream live (`STUDENT_MESSAGE_NEW`) to the lecturer's **Student Messages / Suggestions** panel with mark-as-read.
   - Offline `localStorage` queue with `Queued (offline)` badge and automatic flush on reconnect.
3. **F3 — Instant KISS Polls (Implemented):**
   - 2–4 option polls with live Chart.js updates and `POST /api/poll/{poll_id}/close`.
4. **F4 — AI Lecture Summary (Implemented):**
   - Parses `.vtt`, `.srt`, `.txt`, `.md` with timestamps; extracts audio via `ffmpeg` and transcribes via OpenAI Whisper or `faster-whisper` (explicitly reporting `Transcription Unavailable` if neither is configured).
   - Chunks long transcripts into 5 structured sections and publishes to the course forum.
5. **F5 — AI Homework Review & Cohort Comparison (Implemented):**
   - Shallow `git clone --depth 1` of GitHub repos, 5-criterion rubric scoring (LLM or `[Non-LLM Static Analysis]`), TF-IDF cosine similarity flagging, cohort percentiles, and student self-submission.

**Goals & Out of Scope:** Designed for a 10-minute single-server classroom demo with zero native app installs and no national ID numbers. University SSO (Moodle), live Zoom webhooks, and native mobile apps are out of scope.

## 3. Architecture

```text
Browser (static/)                         FastAPI process (app/)                  Storage
┌──────────────────────────┐   REST    ┌─────────────────────────────────┐   ┌──────────────────┐
│ login / lecturer /       │ ────────▶ │ routers/  → services/           │ ─▶│ data/smartclass.db│
│ student / forum pages    │           │  attendance · quiz · poll · AI  │   │ (SQLite, WAL)    │
│ api.js (Axios)           │ ◀──────── │ ws_manager (in-memory sockets)  │   │ uploads/         │
│ ws.js  (WebSocket)       │  /ws/{id} │ YOLOv8n + ByteTrack (optional)  │   │ reports/ (CSV)   │
└──────────────────────────┘           └─────────────────────────────────┘   └──────────────────┘
```

| Layer | Technology |
| :--- | :--- |
| Backend | Python 3.10+ (Docker: 3.11), FastAPI, Uvicorn (single worker), WebSockets |
| Database | SQLite (WAL) + SQLAlchemy 2.0 |
| Vision & data | Ultralytics YOLOv8n, ByteTrack, OpenCV headless, pandas, openpyxl |
| AI | OpenAI API (`gpt-4o-mini`), offline fallback |
| Frontend | HTML, Tailwind CSS (CDN), vanilla ES6 modules, Axios, QRCode.js, Chart.js |
| Deployment | Docker + Docker Compose (CPU-only PyTorch) |

## 4. Repository layout

```text
app/            FastAPI backend: main.py, config, database, models, schemas, routers/, services/
static/         Frontend pages (*.html) and js/ modules
tests/          pytest suite (conftest.py isolates DB, files, YOLO and OpenAI)
docs/           Backend, frontend and Docker docs + assignment specs
data/           SQLite database (created at runtime, git-ignored)
uploads/        Uploaded Excel banks and lecture files (runtime)
reports/        Exported attendance CSVs (runtime)
Dockerfile, docker-compose.yml, .env.example, requirements.txt
```

---

## 5. Quick start

### Option A: Docker (recommended)

```bash
cp .env.example .env            # optional: add OPENAI_API_KEY
docker compose up --build -d
```

Details, volumes and production notes: [docs/docker.md](docs/docker.md).

### Option B: Local Python

Requires **Python 3.10+**. Run everything from the project root.

```bash
python -m venv .venv
# Windows (PowerShell): .venv\Scripts\Activate.ps1
# Windows (cmd):        .venv\Scripts\activate.bat
# macOS/Linux:          source .venv/bin/activate
pip install -r requirements.txt
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

- To use your `.env` locally, add `--env-file .env`. The app does not read `.env` by itself.
- `requirements.txt` includes `ultralytics`, which pulls in PyTorch (large). Without it the app still runs, using the mock tracker.

### Open the app

| URL | What |
| :--- | :--- |
| `http://localhost:8000/` | Login (students and lecturers) |
| `/lecturer_dashboard` | Lecturer control center |
| `/student_dashboard` | Student view (or scan a quiz QR: `/s/{token}`) |
| `/forum` | Course forum |
| `/docs` | Interactive API docs (Swagger) |

On first start the app creates `data/smartclass.db`, three sample courses, and the default lecturer.

### A 2-minute tour

1. Log in as the lecturer **`111111111` / `admin123`**.
2. In another browser or a private window, log in as a student (any ID, e.g. `300000001`) and request to join a course.
3. As the lecturer, open **Pending Enrollments** and approve the student.
4. Both open **Forum** and post in that course.
5. As the lecturer:
   - upload an Excel bank (columns `Question | A | B | C | D | Correct`);
   - launch a question and open the QR link as the student;
   - watch the chart update.

---

## 6. Accounts

- **Students** log in with their ID only. A profile is created on first login.
- **Lecturers** log in with ID + password. An unused ID with a password creates a new lecturer account.
- An ID belongs to one role; logging in as the other role is refused.

### Default lecturer

Created at startup if the ID doesn't exist yet. The sample courses that have no lecturer are assigned to it.

| Variable | Default |
| :--- | :--- |
| `DEFAULT_LECTURER_ID` | `111111111` |
| `DEFAULT_LECTURER_NAME` | `Default Lecturer` |
| `DEFAULT_LECTURER_PASSWORD` | `admin123` |

- **Docker:** edit these in `docker-compose.yml`. **Local:** set them in the environment or `.env` (with `--env-file`).
- **Change the password before deploying anywhere public.**
- The password is only used when the account is **created**. Changing it later has no effect on an existing account.
- A new `DEFAULT_LECTURER_ID` creates a new lecturer, but courses already assigned to the old one stay there. Move them with:

  ```http
  PATCH /api/courses/{course_id}/lecturer
  { "acting_lecturer_id": "<your lecturer ID>", "lecturer_id": "<new lecturer ID>" }
  ```

  The new lecturer must have logged in at least once.
- Setting `DEFAULT_LECTURER_ID` to an empty value disables the default lecturer.

> **Security note.** Login state lives in the browser (`localStorage`). There are no session tokens, and most endpoints trust the caller. This suits a classroom demo on a trusted network, not the open internet. See [docs/backend.md §5](docs/backend.md#5-authentication-and-access-control).

## 7. Configuration

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `DATABASE_URL` | `data/smartclass.db` in the project | SQLAlchemy URL, e.g. `sqlite:///./data/smartclass.db` |
| `SECRET_KEY` | `supersecret_kiss_key` | Salt for lecturer password hashes. Changing it invalidates existing lecturer passwords. |
| `OPENAI_API_KEY` | *(empty)* | Enables real LLM summaries; otherwise an offline fallback is used |
| `DEFAULT_LECTURER_*` | see above | Default lecturer account |

## 8. Tests

```bash
python -m pytest -q
```

About 80 tests cover:

- auth and startup seeding;
- enrollment and the course forum's access rules;
- quiz expiry, polls, attendance and CSV export;
- the AI endpoints and WebSocket events;
- that the frontend's API calls match real backend routes.

Each test runs on its own temporary database, so your `data/smartclass.db` is never touched. Details: [docs/backend.md §9](docs/backend.md#9-tests).

## 9. Known limitations

- Audio/video transcription requires `OPENAI_API_KEY` (Whisper API) or local `faster-whisper`; otherwise the endpoint explicitly returns `Transcription Unavailable` (`.vtt`/`.srt`/`.txt` work offline).
- Homework review uses `[Non-LLM Static Analysis]` + local TF-IDF similarity when `OPENAI_API_KEY` is unset.
- Runs as a single process (in-memory WebSockets and ByteTrack state). Don't scale to several workers.
- Login state lives in `localStorage` (suitable for a trusted-LAN classroom demo, not public internet hosting).

## 10. Troubleshooting

- **`ModuleNotFoundError: No module named 'app'`:** run from the project root, and use `python -m uvicorn ...`.
- **`uvicorn: command not found` / wrong packages:** the virtual environment isn't active. Activate it, or run `.venv\Scripts\python -m uvicorn ...`.
- **PowerShell refuses to run `Activate.ps1`:** run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- **Default lecturer password rejected:** the account was created earlier with another password or `SECRET_KEY`. Reset the database.
- **Start over with a clean database:** stop the server and delete `data/smartclass.db` (plus the `-wal` / `-shm` files). It is recreated and re-seeded on the next start.
- **Phones can't open quiz QR codes:** open the lecturer dashboard via your computer's LAN IP instead of `localhost`. The QR uses the address in the browser bar.
- Docker-specific problems: [docs/docker.md §6](docs/docker.md#6-troubleshooting).
