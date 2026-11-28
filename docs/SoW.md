# Statement of Work (SoW)

**Project:** SmartClass AI — Web-Based Teaching & Classroom Analytics Platform  
**Course:** Introduction to Software Engineering (Ex2: OOP / OOD)  
**Institution:** Ariel University  

---

## 1. Background

Academic lectures often suffer from slow manual roll-call, low real-time student engagement, and manual post-class effort to summarize recordings and review code assignments. **SmartClass AI** provides a lightweight, single-server web suite built around the **KISS** principle so a lecturer can run attendance, interactive quizzes/polls, a course forum, and AI-assisted reviews from a single laptop or Docker container.

---

## 2. Objectives

1. Automate classroom attendance counting and dwell-time tracking via computer vision and frictionless QR self check-in, exporting both online tables and offline `.csv`/`.xlsx` spreadsheets.
2. Enable real-time student participation (5-minute time-gated QR quizzes, 1-click KISS polls, course forum threads/replies, and private suggestions) with offline resilience.
3. Automate post-lecture `.vtt`/`.srt`/audio summarization into the course forum and provide rubric-based + cohort-comparative homework code reviews.
4. Deliver complete OOP/OOD design documentation and an automated `pytest` verification suite.

---

## 3. Scope

### In Scope
- Single-process FastAPI + SQLite (`WAL` mode) backend with REST and WebSocket endpoints.
- Zero-build static HTML5/Tailwind/Vanilla JS frontend for Lecturers and mobile Students.
- YOLOv8n + ByteTrack image/video person tracking and photo counting (with graceful mock fallback).
- Student self check-in QR, 5-minute timed Excel quizzes, instant closeable polls, real-time course forum, and private lecturer inbox.
- Lecture summarization (`.txt`, `.md`, `.vtt`, `.srt`, plus `ffmpeg` + Whisper/`faster-whisper` for media).
- GitHub homework repository shallow cloning, 5-criterion rubric scoring, static metrics fallback, and TF-IDF cohort similarity comparison.
- Docker & Docker Compose packaging and 10-minute in-class demo script (`DEMO.md`).

### Out of Scope
- University SSO integration (Moodle / מידע אישי).
- Live Zoom/Meet cloud webhooks.
- Native iOS/Android mobile applications.
- Storing national ID numbers or biometric facial embeddings.

---

## 4. Deliverables & Milestones

| Phase | Deliverable | Status |
| :--- | :--- | :--- |
| **Phase 1: Core & Gaps** | FastAPI + SQLite schema, F1–F5 backend & frontend, offline queue, `.xlsx` export, real repo review, 92 `pytest` tests | Complete |
| **Phase 2: Design Docs** | `README.md`, `tools-report.md`, `SoW.md`, `SRS.md`, `use-cases.md`, `components.md`, `class-diagrams.md`, `sequence-diagrams.md`, `testing-strategy.md`, updated `backend.md`/`frontend.md`/`docker.md` | Complete |
| **Phase 3: Conclusion & Demo** | `docs/conclusion.md`, `DEMO.md`, final Docker & live classroom verification | Complete (awaiting live demo measurements) |

---

## 5. Team Roles

| Role | Member | Responsibilities |
| :--- | :--- | :--- |
| **Backend & CV / AI Lead** | **TODO:** Fill in team member name | FastAPI routers, SQLite migrations, `AttendanceManager`, `AIServiceAgent`, `pytest` suite |
| **Frontend & UX Lead** | **TODO:** Fill in team member name | Tailwind UI, `api.js`, `ws.js`, offline queue, mobile QR flows, `DEMO.md` execution |
| **Architecture & QA Lead** | **TODO:** Fill in team member name | Design docs, Mermaid diagrams, Docker Compose testing, real-world tool benchmarks |

---

## 6. Assumptions, Constraints & Risks

- **Assumptions:** Lecturer and student phones share a LAN or public URL; Docker or Python 3.10+ is available on the host.
- **Constraints:** Must run with **1 Uvicorn worker** because WebSocket connections and ByteTrack trajectories live in process memory; no React/npm build step; no personal ID numbers required.
- **Risks & Mitigations:**
  - *Classroom Wi-Fi blocks LAN port 8000* → Fallback to localhost dual-browser demo or mobile hotspot.
  - *Webcam unavailable* → Fallback to single class photo counter or pre-recorded `.mp4` upload.
  - *No `OPENAI_API_KEY` or Whisper model* → `.vtt`/`.srt` summaries and `[Non-LLM Static Analysis]` + TF-IDF homework comparison still work offline.

---

## 7. Acceptance Criteria

1. All automated `pytest` tests pass (`python -m pytest -q`).
2. `docker compose up --build -d` serves `/`, `/lecturer_dashboard`, `/student_dashboard`, `/forum`, and `/docs`.
3. All 5 features (F1–F5) execute end-to-end within the 10-minute `DEMO.md` script.
