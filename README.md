# SmartClass AI: Web-Based Teaching & Classroom Analytics Platform

**Course:** Introduction to Software Engineering (Ex2: OOP / OOD)  
**Institution:** Ariel University  
**Authors:** Ron Perelman (212418735) & Shlomo Toussia-Cohen (331294710)

SmartClass AI is a single-server web app for running a lecture:

- attendance from a classroom camera;
- 5-minute QR quizzes;
- live polls;
- a per-course forum;
- AI lecture summaries and homework reviews.

It follows **KISS**: one FastAPI process, one SQLite file, and a static frontend with no build step.

| Documentation | |
| :--- | :--- |
| **This file** | Overview, quick start, accounts, configuration |
| [docs/backend.md](docs/backend.md) | Architecture, data model, full REST + WebSocket reference, tests |
| [docs/frontend.md](docs/frontend.md) | Pages, JS modules, login state, conventions |
| [docs/docker.md](docs/docker.md) | Image, Compose, volumes, deployment, troubleshooting |

Assignment documents (requirements and design, written before implementation): [SRS](docs/software_requirements_specification.md), [technical blueprint](docs/technical_system_blueprint.md), [extended spec (Hebrew)](docs/extended_system_specification.md), [original project readme](docs/project_readme.md).

---

## 1. Problem

- **Attendance** by roll-call wastes 5–15 minutes, and sign-in sheets or static QR codes let students sign in and leave.
- **Lectures are passive.** Lecturers lack quick, zero-install ways to check understanding.
- **After the lecture,** writing summaries and giving consistent OOD/SOLID feedback on homework is slow.

## 2. Features

1. **Visual attendance.**
   - Classroom images (webcam frames from the browser, or uploads) go through **YOLOv8n + ByteTrack**.
   - Time seen in the room is compared with a `PresencePolicy` (default: present ≥ 70% of the session).
   - Export to CSV.
   - When the vision libraries aren't available, a mock tracker is used.
2. **5-minute QR quizzes.**
   - Upload an Excel question bank and launch a question; it shows as a QR code (`/s/{token}`) for 300 seconds.
   - After that, answers are rejected (`410` / `403`).
   - You get an alert when the bank is used up.
   - Each answer is linked to an attendance track.
3. **Live polls** with 2–4 options. Results update live over WebSockets.
4. **Course forum.**
   - Threads and replies per course, for the course's lecturer and its approved students.
   - Students can also send private messages to the lecturer.
5. **AI workflows.**
   - Lecture summary from a recording or transcript, posted to the summary feed.
   - Comparative OOD/SOLID review of homework repository URLs.
   - Uses OpenAI when `OPENAI_API_KEY` is set, otherwise a fixed offline answer.

**Out of scope:** university SSO (Moodle), live Zoom/Meet webhooks, native mobile apps (students use the mobile browser).

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

- Audio/video lecture files are not transcribed. Summaries of recordings use a placeholder transcript; `.txt` / `.md` transcripts are used as-is.
- Homework review does not download the repositories; scores are generated from the URLs.
- Uploaded video files are not run through YOLO (only still images are); they fall back to the mock tracker.
- Private student messages are stored, but no page shows them to the lecturer yet (`GET /api/forum/posts?post_type=private_message`).
- The forum does not update live; reload or switch course to see new posts.
- Runs as a single process (in-memory WebSockets and tracking state). Don't scale to several workers.

## 10. Troubleshooting

- **`ModuleNotFoundError: No module named 'app'`:** run from the project root, and use `python -m uvicorn ...`.
- **`uvicorn: command not found` / wrong packages:** the virtual environment isn't active. Activate it, or run `.venv\Scripts\python -m uvicorn ...`.
- **PowerShell refuses to run `Activate.ps1`:** run `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once.
- **Default lecturer password rejected:** the account was created earlier with another password or `SECRET_KEY`. Reset the database.
- **Start over with a clean database:** stop the server and delete `data/smartclass.db` (plus the `-wal` / `-shm` files). It is recreated and re-seeded on the next start.
- **Phones can't open quiz QR codes:** open the lecturer dashboard via your computer's LAN IP instead of `localhost`. The QR uses the address in the browser bar.
- Docker-specific problems: [docs/docker.md §6](docs/docker.md#6-troubleshooting).
