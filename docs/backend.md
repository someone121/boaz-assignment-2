# Backend

The backend is a single FastAPI app (`app/`) backed by one SQLite file. It serves the REST API, one WebSocket endpoint, and the static frontend pages.

- Entry point: [app/main.py](../app/main.py) (`app.main:app`)
- Python 3.10+ (the Docker image uses 3.11)
- Interactive API docs while the server runs: `http://localhost:8000/docs`

See also: [frontend.md](frontend.md) · [docker.md](docker.md) · [../README.md](../README.md)

---

## 1. Layout

```text
app/
├── main.py            App setup, startup seeding, page routes, auth, sessions
├── config.py          Settings from environment variables + folder paths
├── database.py        Engine (WAL, foreign keys), get_db dependency, init_db + migrations
├── models.py          SQLAlchemy ORM tables
├── schemas.py         Pydantic request/response models
├── routers/           HTTP layer: validates input, calls services, broadcasts events
│   ├── attendance.py  /api/attendance/*
│   ├── courses.py     /api/courses, /api/enroll/*
│   ├── quiz.py        /api/quiz/*
│   ├── polls.py       /api/poll/*
│   ├── forum.py       Course forum (/api/courses/{id}/posts, /api/posts/{id}/comments) + legacy /api/forum/*
│   ├── ai.py          /api/ai/*
│   └── ws.py          /ws/{session_id}
└── services/          Domain logic, no HTTP routing
    ├── attendance_service.py  PresencePolicy strategies, VisionTracker, AttendanceManager
    ├── quiz_service.py        TimedTokenManager, QuizSessionManager (Excel import, 5-min tokens)
    ├── poll_service.py        Poll creation, voting, tallies
    ├── ai_service.py          Lecture summary + homework review (OpenAI or offline fallback)
    └── ws_manager.py          In-memory WebSocket ConnectionManager
```

Requests flow **router → service → SQLAlchemy session**. Routers that change live state then call `ws_manager.broadcast_event(...)` so open dashboards update.

---

## 2. Configuration

All settings live in [app/config.py](../app/config.py) and are read **once, at import time**, from environment variables.

| Variable | Default | Notes |
| :--- | :--- | :--- |
| `DATABASE_URL` | `sqlite:///<project>/data/smartclass.db` | Any SQLAlchemy URL. The SQLite pragmas are only applied to `sqlite` URLs. |
| `SECRET_KEY` | `supersecret_kiss_key` | Salt for lecturer password hashes. Changing it makes every existing lecturer password stop working. |
| `OPENAI_API_KEY` | *(empty)* | When set, summaries use `gpt-4o-mini`. When empty or the call fails, a fixed offline summary is returned. |
| `DEFAULT_LECTURER_ID` | `111111111` | Seeded at startup. Set to an empty string to disable. |
| `DEFAULT_LECTURER_NAME` | `Default Lecturer` | |
| `DEFAULT_LECTURER_PASSWORD` | `admin123` | Only used when the account is first created. |

Hard-coded constants: `QUIZ_TOKEN_TTL_SECONDS = 300` and `DEFAULT_PRESENCE_THRESHOLD = 0.70`.

The app does **not** load `.env` by itself. Locally, pass it to uvicorn with `--env-file .env`. Docker Compose reads it for you (see [docker.md](docker.md)). `APP_HOST` / `APP_PORT` in `.env.example` are not read by the code.

Runtime folders (created automatically): `data/`, `uploads/`, `reports/`, `static/`.

---

## 3. Startup

`lifespan()` in `main.py` runs once when the server starts:

1. **`init_db()`**: creates missing tables, then applies small `ALTER TABLE` migrations for older databases (`sessions.total_detected`, `sessions.students_left_early`, `forum_posts.course_id` + index, `forum_posts.title`). There is no Alembic; add new columns here the same way.
2. **`_seed_default_courses()`**: if the `courses` table is empty, inserts the three sample courses.
3. **`_seed_default_lecturer()`**:
   - creates the `DEFAULT_LECTURER_ID` user if the ID is free;
   - assigns the sample courses that have **no** lecturer to them;
   - skips everything (with a warning) if the ID belongs to a student;
   - never changes an existing user's password.

`SessionLocal` uses `autoflush=False`, so the new lecturer is flushed before the bulk course `UPDATE`. Without it SQLite's foreign key check fails and startup crashes.

SQLite connections run with `journal_mode=WAL`, `foreign_keys=ON` and `busy_timeout=5000` so many students can submit at the same moment.

---

## 4. Data model

| Table | Model | Purpose |
| :--- | :--- | :--- |
| `users` | `User` | Login profile. `role` is `student` or `lecturer`; `password_hash` only for lecturers. |
| `students` | `Student` | Student registry used by enrollments, quiz submissions, attendance. Created on student login, enrollment or quiz submit. |
| `courses` | `Course` | Course with optional `lecturer_id`. |
| `enrollments` | `Enrollment` | `pending` or `approved` link between student and course. |
| `sessions` | `LectureSession` | One lecture. Holds start/end time and final attendance counts. |
| `attendance_records` | `AttendanceRecord` | Dwell seconds per tracked person (`track_id`) per session, optionally linked to a student. |
| `quiz_questions` | `QuizQuestion` | Imported from Excel. `is_used` flips when triggered. |
| `active_question_tokens` | `ActiveQuestionToken` | The QR token; valid until `expires_at`. |
| `quiz_submissions` | `QuizSubmission` | A student's answer with `is_correct`. |
| `polls` / `poll_votes` | `Poll`, `PollVote` | 2–4 option polls and their votes. |
| `forum_posts` | `ForumPost` | Course threads (`course_id` + `title` set) **and** legacy feed entries (AI summaries, private messages; `course_id` is NULL). |
| `forum_comments` | `ForumComment` | Replies to course threads (cascade-deleted with the post). |
| `lecture_summaries` | `LectureSummary` | AI summaries and their transcript. |
| `homework_reviews` | `HomeworkReview` | AI homework scores and feedback. |

All timestamps are stored as naive UTC (`models.utcnow()`).

---

## 5. Authentication and access control

This is a local / classroom demo, not a hardened system. Know these limits before deploying:

- **No tokens or cookies.** `POST /api/auth/login` returns the user profile. The frontend keeps it in `localStorage` and sends the user's ID in later requests.
- **Login rules** (`login_or_register`):
  - Students: ID only. Unknown IDs are registered automatically.
  - Lecturers: ID + password. An unused ID is registered as a lecturer; a wrong password gives `401`.
  - An ID registered as one role cannot log in as the other (`403`).
  - Without `role`, sending a password means lecturer.
  - Passwords are stored as `sha256(SECRET_KEY + ":" + password)`.
- **Server-side checks exist only on:**
  - the course forum: the caller's role is read from the `users` table. Lecturers must teach the course; students need an `approved` enrollment. Otherwise `403` (`401` for an unknown ID);
  - `PATCH /api/courses/{id}/lecturer`: the acting user must be a lecturer.
- All other endpoints (sessions, quizzes, polls, attendance, AI, enrollment approval) trust the caller.
- CORS allows every origin.

---

## 6. REST API

Bodies are JSON unless marked **form** (`multipart/form-data`). Errors return `{"detail": "..."}`; Pydantic validation errors return `422`.

### Core, auth, sessions ([main.py](../app/main.py))

| Method | Path | Body / params | Returns |
| :--- | :--- | :--- | :--- |
| GET | `/api/health` | | `{status, app, version, database}` |
| POST | `/api/auth/login` | `{id_number \| user_id, full_name?, role?, password?, email?}` | User profile. `400` no ID / lecturer without password, `401` wrong password, `403` role mismatch |
| POST | `/api/session/start` | `{course_name, course_id?, lecturer_id?}` | New active session |
| GET | `/api/sessions` | | All sessions, newest first |
| GET | `/api/sessions/{session_id}/report` | | Attendance summary. Before any frame is uploaded it returns demo numbers with `is_mock_data: true`. `404` unknown session |

### Courses and enrollment ([routers/courses.py](../app/routers/courses.py))

| Method | Path | Body / params | Returns |
| :--- | :--- | :--- | :--- |
| GET | `/api/courses` | `?student_id=` (optional) | All courses. With `student_id`, each has that student's `enrollment_status` (`pending`, `approved` or `null`) |
| POST | `/api/courses` | `{name, lecturer_id?}` | New course |
| PATCH | `/api/courses/{course_id}/lecturer` | `{acting_lecturer_id, lecturer_id}` | Updated course. `403` actor is not a lecturer, `400` target is not an existing lecturer, `404` course |
| POST | `/api/enroll` | `{student_id, course_id}` | `pending` enrollment. Asking again returns the existing one. `404` course |
| GET | `/api/enroll/pending` | | All pending enrollments (every course) |
| POST | `/api/enroll/approve` | `{enrollment_id}` or `{student_id, course_id}` | Approved enrollment. `400` missing identifiers, `404` not found |

### Course forum ([routers/forum.py](../app/routers/forum.py))

Plain REST, no WebSocket events. Access rules: section 5.

| Method | Path | Body / params | Returns |
| :--- | :--- | :--- | :--- |
| GET | `/api/courses/{course_id}/posts` | `?user_id=` (required) | Threads newest first, each with `comments` oldest first |
| POST | `/api/courses/{course_id}/posts` | `{author_id, title, content}` | `201` thread. `400` blank title/content |
| POST | `/api/posts/{post_id}/comments` | `{author_id, content}` | `201` reply. `404` if the post doesn't exist or isn't a course thread |

Author name and role are copied from the `users` table, not from the request.

### Legacy forum feed

| Method | Path | Body / params | Returns |
| :--- | :--- | :--- | :--- |
| GET | `/api/forum/posts` | `?session_id=&post_type=` | Posts newest first (includes course threads unless filtered) |
| POST | `/api/forum/posts` | `{author_name, content, post_type?, author_role?, session_id?, author_id?, recipient_id?, course_name?}` | New post. Broadcasts `NEW_FORUM_POST` unless `post_type` is `private_message` |

Used for AI summaries (`ai_summary`) and student → lecturer private messages (`private_message`).

### Attendance ([routers/attendance.py](../app/routers/attendance.py))

| Method | Path | Body / params | Returns |
| :--- | :--- | :--- | :--- |
| POST | `/api/attendance/frame` | **form** `session_id`, `file`, `interval_seconds` (default 5) | `{detected_count, active_track_ids, total_tracked_unique, detector_mode}` |
| GET | `/api/attendance/status/{session_id}` | | `{total_tracked, records[]}` with `presence_status` per track |
| POST | `/api/attendance/stop` | `?session_id=` | Closes the session, writes the CSV, broadcasts `ATTENDANCE_DONE` |
| GET | `/api/attendance/export` | `?session_id=` | CSV file download (`attendance_<id>.csv`) |

### Quiz ([routers/quiz.py](../app/routers/quiz.py))

| Method | Path | Body / params | Returns |
| :--- | :--- | :--- | :--- |
| POST | `/api/quiz/upload-excel` | **form** `file` (.xlsx), `session_id?` | `{loaded_count, questions[]}`. `400` empty sheet / no rows |
| GET | `/api/quiz/questions` | | `{total, remaining, questions_exhausted, questions[]}` |
| POST | `/api/quiz/trigger` | `{session_id, question_id?, lecturer_id?}` | Token, question, `qr_path` (`/s/{token}`), `expires_at`, `remaining_questions`. Without `question_id` takes the next unused one. `404` bank empty |
| GET | `/api/quiz/token/{token}` | | Question + non-empty options + `seconds_remaining`. `404` unknown, **`410`** expired |
| POST | `/api/quiz/submit` | `{token, student_id, full_name, selected_option}` | `{is_correct, total_responses, option_counts}`. **`403`** expired. Broadcasts `QUIZ_UPDATE` |

**Excel format:** columns `Question | A | B | C | D | Correct` on the first sheet. A header row is detected and skipped when the first row contains `question`, `question_text` or `prompt`. Missing A/B default to `True`/`False`; missing correct answer defaults to `A`.

A quiz submit also links the student to one unassigned attendance track in that session.

### Polls ([routers/polls.py](../app/routers/polls.py))

| Method | Path | Body / params | Returns |
| :--- | :--- | :--- | :--- |
| POST | `/api/poll/create` | `{session_id, prompt, option_1, option_2, option_3?, option_4?}` | `{poll_id, options, results, total_votes, is_open}`. Broadcasts `POLL_UPDATE` |
| GET | `/api/poll/{session_id}` | | Session polls with tallies, newest first |
| POST | `/api/poll/vote` | `{poll_id, selected_option, student_id?}` | Updated tallies. `400` invalid option, `403` closed, `404` unknown. Broadcasts `POLL_UPDATE` |

`selected_option` is the option **text**, not a letter.

### AI ([routers/ai.py](../app/routers/ai.py))

| Method | Path | Body / params | Returns |
| :--- | :--- | :--- | :--- |
| POST | `/api/ai/summarize-lecture` | **form** `file`, `session_id?`, `course_name?` | `{summary_id, forum_post_id, markdown_summary}`. Also creates an `ai_summary` feed post and broadcasts `SUMMARY_READY` + `NEW_FORUM_POST` |
| GET | `/api/ai/summaries` | | Stored summaries |
| POST | `/api/ai/review-homework` | `{repo_urls[], session_id?}` | `{count, reviews[]}`; blank URLs are skipped |
| GET | `/api/ai/reviews` | | Stored reviews |

What is real and what is simulated:

- `.txt` / `.md` uploads are used as the transcript.
- Audio and video are **not** transcribed; a placeholder transcript is used.
- Homework reviews do **not** fetch the repository; score and feedback are generated from the URL.

### Page routes (not in OpenAPI)

| Path | Serves |
| :--- | :--- |
| `/`, `/login` | `static/login.html` |
| `/lecturer_dashboard`, `/dashboard` | `static/lecturer_dashboard.html` |
| `/student_dashboard`, `/live`, `/s/{token}` | `static/student_dashboard.html` |
| `/forum` | `static/forum.html` |
| `/static/*` | Files under `static/` |

---

## 7. WebSocket

`ws://<host>/ws/{session_id}` (`wss://` behind HTTPS). The server only sends; anything the client sends is ignored.

Messages are `{"event": "<TYPE>", "data": {...}}`. Each event is sent to the channel of its session **and** to everyone on the `global` channel.

| Event | Sent by | `data` |
| :--- | :--- | :--- |
| `QUIZ_UPDATE` | quiz submit | `{total_responses, option_counts}` |
| `POLL_UPDATE` | poll create / vote | `{poll_id, prompt, results}` |
| `SUMMARY_READY` | lecture summary | `{session_id, markdown_summary}` |
| `NEW_FORUM_POST` | legacy feed post, lecture summary | `{id, author, author_role, post_type, content, timestamp}` |
| `ATTENDANCE_DONE` | attendance stop | `{download_url, total_present}` |

Connections are kept in process memory ([ws_manager.py](../app/services/ws_manager.py)), so the server must run with **one worker**.

---

## 8. Attendance engine

[attendance_service.py](../app/services/attendance_service.py):

- **`PresencePolicy`** (strategy):
  - `PercentagePresencePolicy(0.70)`, the default: present if `dwell / session length >= 70%`;
  - `FixedTimePresencePolicy(minutes)`: present after a fixed number of minutes.
- **`VisionTracker`**: on first use, tries to load `ultralytics` + OpenCV + `yolov8n.pt` and runs YOLO person detection with ByteTrack.
  - If loading fails, or the upload cannot be decoded as an image (for example `.mp4` video), it falls back to a **mock** that returns 3–7 fake tracks.
  - `detector_mode` in the frame response shows which one ran.
- **`AttendanceManager`**: adds `interval_seconds` of dwell time per detected track on every frame, saves `AttendanceRecord` rows, closes the session on stop and exports CSV with pandas to `reports/`.
  - ByteTrack track state and session start times live **in memory**, so a restart restarts the tracking clock.

---

## 9. Tests

```bash
python -m pytest -q
```

[tests/conftest.py](../tests/conftest.py) gives every test:

- a fresh temporary SQLite database, shared by request handlers **and** startup seeding;
- temporary `uploads/` and `reports/` folders;
- the mock tracker and no OpenAI key.

Your real `data/smartclass.db` is never touched.

| File | Covers |
| :--- | :--- |
| `test_presence_policy.py` | Policy thresholds |
| `test_quiz_tokens.py` | 300 s token expiry boundaries |
| `test_excel_parser.py` | Excel import |
| `test_auth_and_seeding.py` | Login rules, default courses/lecturer, restart idempotency, no student promotion |
| `test_courses_and_enrollment.py` | Courses, pending → approved flow, lecturer reassignment |
| `test_course_forum.py` | Threads, replies, ordering, access control (401/403/404) |
| `test_quiz_and_polls_api.py` | Trigger, expiry (410/403), exhaustion, poll voting errors |
| `test_sessions_attendance_ai.py` | Session reports, frame accumulation, stop/export CSV, quiz ↔ track linking, AI endpoints |
| `test_websocket.py` | ConnectionManager fan-out, dead sockets, live `POLL_UPDATE` / `ATTENDANCE_DONE` |
| `test_frontend_contract.py` | Page routes, every script/import exists, every `api.js` URL has a backend route |
| `test_api_integration.py` | One end-to-end classroom run including 20 concurrent quiz submissions |

Shared helpers (`login_student`, `login_lecturer`, `create_course`, `enroll`, `start_session`) live in `conftest.py`.

---

## 10. Adding a feature

1. Add the table/columns in `models.py`. For an **existing** table, also add an `ALTER TABLE` step to `init_db()` so old databases upgrade.
2. Add request/response models in `schemas.py`.
3. Put the logic in `services/`, and the endpoint in a router under `routers/`. Register new routers in `main.py`.
4. If dashboards should update live, call `ws_manager.broadcast_event(session_id, "EVENT", data)` and handle it in the frontend (see [frontend.md](frontend.md)).
5. Add a wrapper in `static/js/api.js`. `test_frontend_contract.py` fails if it points at a route that doesn't exist.
6. Add tests using the `client` / `db` fixtures.
