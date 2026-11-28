# Software Requirements Specification (SRS — IEEE 830 Style)

**Project:** SmartClass AI  
**Version:** 2.0  

---

## 1. Introduction

### 1.1 Purpose
This SRS defines the functional, non-functional, interface, and traceability requirements for **SmartClass AI**, a web-based classroom management and active-learning tool.

### 1.2 Scope
SmartClass AI operates as a single-process FastAPI server with an embedded SQLite database and a zero-build mobile/desktop web frontend. It covers automated attendance (F1), real-time/offline forum & suggestions (F2), instant polls (F3), lecture video/transcript summarization (F4), and comparative homework code review (F5).

---

## 2. Overall Description

### 2.1 User Classes
1. **Lecturer:** Starts/stops lecture sessions, triggers attendance check-in QRs, uploads classroom photos/videos, launches 5-minute quizzes, creates/closes polls, uploads lecture recordings/transcripts, reviews homework cohorts, approves course enrollments, and reads student private messages.
2. **Student:** Logs in via demo ID/name (no personal ID numbers required), requests course enrollment, scans check-in or quiz QRs on a mobile browser, votes in live polls, participates in the course forum (online or queued offline), sends private messages, and submits/views their own homework review.

### 2.2 Operating Environment & Constraints
- **Server:** Python 3.10+ (Docker: `python:3.11-slim`), single Uvicorn worker (`--workers 1`).
- **Database:** SQLite in WAL mode (`foreign_keys=ON`, `busy_timeout=5000`).
- **Clients:** Modern desktop and mobile web browsers (Chrome, Safari, Firefox).

---

## 3. Functional Requirements

### F1: Attendance & Quizzes
- **FR-1.1:** The system shall ingest classroom images and browser webcam frames (`POST /api/attendance/frame`) and run YOLOv8n + ByteTrack person tracking (falling back to mock only if YOLO cannot load).
- **FR-1.2:** For uploaded videos (`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`), the system shall sample frames via OpenCV every `N` seconds and run YOLO + ByteTrack, reporting `detector_mode: "yolo_video"`.
- **FR-1.3:** `AttendanceManager` shall evaluate dwell eligibility using a `PresencePolicy` strategy (`PercentagePresencePolicy` ≥ 70% default, or `FixedTimePresencePolicy`).
- **FR-1.4:** `GET /api/sessions/{session_id}/report` shall return real counts, or zeros with `no_data: true` when no data exists (returning mock numbers only when `DEMO_MODE=true`).
- **FR-1.5:** Lecturers shall trigger a short-lived self check-in QR (`POST /api/attendance/checkin/trigger`); students shall scan `/checkin/{token}` and submit `"I'm here"` (`POST /api/attendance/checkin/submit`).
- **FR-1.6:** The system shall export unified attendance (camera + self check-in) to both `.csv` (`/api/attendance/export`) and `.xlsx` (`/api/attendance/export-xlsx`) with columns `student_id, name, checked_in_at, camera_dwell_minutes, presence_status, source`.
- **FR-1.7:** `POST /api/attendance/count-photo` shall count people in a single class photo and return bounding boxes and an annotated image.
- **FR-1.8:** Lecturers shall upload `.xlsx` quiz banks, trigger 300-second QR tokens (`/s/{token}`), receive exhaustion alerts, and view live `QUIZ_UPDATE` charts; late submissions shall be rejected (`403` / `410`).
- **FR-1.9:** `GET /api/config` shall expose `PUBLIC_BASE_URL` so QR codes can target the host's LAN IP while the lecturer keeps `http://localhost:8000` open for browser webcam (`getUserMedia`) access.

### F2: Comments, Course Forum & Suggestions
- **FR-2.1:** Lecturers and approved students shall read and create course-scoped threads and replies (`GET/POST /api/courses/{id}/posts`, `POST /api/posts/{id}/comments`).
- **FR-2.2:** New threads and replies shall broadcast `FORUM_THREAD_NEW` and `FORUM_COMMENT_NEW` over `/ws/course:{course_id}` so connected clients update live.
- **FR-2.3:** Students shall submit private messages/suggestions (`post_type="private_message"`), which broadcast `STUDENT_MESSAGE_NEW` to the lecturer dashboard and can be marked read (`POST /api/forum/posts/{id}/read`).
- **FR-2.4:** When offline, failed forum posts/replies and private messages shall queue in `localStorage`, display a `Queued (offline)` badge, and flush automatically on reconnect.

### F3: Live Polls
- **FR-3.1:** Lecturers shall create 2–4 option polls (`POST /api/poll/create`) and close them (`POST /api/poll/{poll_id}/close`), broadcasting `POLL_UPDATE` with `is_open`.
- **FR-3.2:** Students shall vote in open polls (`POST /api/poll/vote`); closed polls shall reject votes (`403`) and display a closed state in the UI.

### F4: Lecture Video & Transcript Summarizer
- **FR-4.1:** `POST /api/ai/summarize-lecture` shall parse `.vtt`, `.srt`, `.txt`, and `.md` files with timestamps preserved.
- **FR-4.2:** For `.mp4`/`.m4a`/`.mp3`/`.wav`, the system shall extract audio via `ffmpeg` and transcribe via OpenAI Whisper API or local `faster-whisper`, or explicitly report `transcription_available: false` (`Transcription Unavailable`) when neither is available.
- **FR-4.3:** Long transcripts shall be chunked and summarized into Main Concepts & Topics, Key Definitions, Timeline with Timestamps, Open Questions, and Suggested Review Exercises, and published to the course forum when `course_id` is linked.

### F5: Homework Comparative Review
- **FR-5.1:** `POST /api/ai/review-homework` shall shallow-clone valid GitHub URLs (`git clone --depth 1`) into a temp directory and inspect README, file tree, LOC, and test files.
- **FR-5.2:** Each repo shall be scored against a 5-criterion rubric (`correctness`, `design_oop`, `code_quality`, `tests`, `documentation`) via LLM or deterministic `[Non-LLM Static Analysis]`.
- **FR-5.3:** Within a batch, the system shall compute pairwise TF-IDF cosine similarity, flag high similarity (`>= 0.85`), compute cohort percentiles, and generate comparative notes without leaking peer code.
- **FR-5.4:** Students shall submit their own repo URL and view their own reviews (`GET /api/ai/reviews?student_id=...`).

### Cross-Cutting: Roster Import
- **FR-6.1:** Lecturers shall import a names-only student roster (`.csv`/`.xlsx`) into a course (`POST /api/courses/{course_id}/import-students`) without personal ID numbers.

---

## 4. Non-Functional Requirements

- **NFR-1 (Usability / KISS):** Zero build step, zero native app install; students reach QR check-in or quiz forms in ≤ 2 taps.
- **NFR-2 (Performance & Concurrency):** SQLite WAL + `busy_timeout=5000` supports 20+ concurrent quiz submissions without lock failures; single photo/frame processing completes in < 1 s on CPU.
- **NFR-3 (Availability for Demo):** Offline fallbacks exist for AI summaries (`.vtt`/`.srt`/static), homework analysis (`[Non-LLM Static Analysis]`), forum posting (`localStorage` queue), and photo/video attendance.
- **NFR-4 (Privacy & Security Limits):** No biometric face embeddings or national ID numbers are required. Because this is a classroom demo, auth state lives in `localStorage` without signed session cookies; server-side role checks enforce course forum access and course reassignment (`backend.md §5`).

---

## 5. External Interfaces

- **REST + WebSocket:** FastAPI HTTP/JSON + `multipart/form-data` uploads + `ws(s)://<host>/ws/{session_id}`.
- **External Services (Optional):** OpenAI API (`gpt-4o-mini`, `whisper-1`), `git` CLI to `github.com`, `ffmpeg` CLI.

---

## 6. Traceability Matrix

| Requirement | Use Case | Component | Test |
| :--- | :--- | :--- | :--- |
| FR-1.1 – FR-1.4 | UC-1 | `VisionTracker`, `AttendanceManager`, `app/main.py` | `test_sessions_attendance_ai.py`, `test_presence_policy.py` |
| FR-1.5 – FR-1.7 | UC-2, UC-3 | `attendance.py`, `AttendanceManager` | `test_phase1_features.py` |
| FR-1.8 | UC-4 | `TimedTokenManager`, `QuizSessionManager` | `test_quiz_tokens.py`, `test_quiz_and_polls_api.py`, `test_api_integration.py` |
| FR-2.1 – FR-2.4 | UC-5, UC-6 | `forum.py`, `ws_manager.py`, `forum.js`, `student.js` | `test_course_forum.py`, `test_phase1_features.py` |
| FR-3.1 – FR-3.2 | UC-7 | `polls.py`, `poll_service.py` | `test_quiz_and_polls_api.py`, `test_phase1_features.py` |
| FR-4.1 – FR-4.3 | UC-8 | `ai.py`, `AIServiceAgent` | `test_sessions_attendance_ai.py`, `test_phase1_features.py` |
| FR-5.1 – FR-5.4 | UC-9 | `ai.py`, `AIServiceAgent` | `test_sessions_attendance_ai.py`, `test_phase1_features.py` |
| FR-6.1 | UC-10 | `courses.py` | `test_phase1_features.py` |
