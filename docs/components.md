# Component Architecture

## 1. Component Diagram

```mermaid
flowchart TB
    subgraph Client["Presentation Layer (static/)"]
        Login["login.html + login.js"]
        Lecturer["lecturer_dashboard.html + lecturer.js"]
        Student["student_dashboard.html + student.js"]
        Forum["forum.html + forum.js"]
        ApiJS["js/api.js (Axios)"]
        WsJS["js/ws.js (SmartClassSocket)"]
        UiJS["js/ui.js (Toast / EmptyState / Escape)"]
    end

    subgraph API["API Layer (app/routers/ & main.py)"]
        Main["main.py (Auth, Sessions, Page Routes)"]
        R_Att["routers/attendance.py"]
        R_Quiz["routers/quiz.py"]
        R_Poll["routers/polls.py"]
        R_Forum["routers/forum.py"]
        R_Course["routers/courses.py"]
        R_AI["routers/ai.py"]
        R_WS["routers/ws.py"]
    end

    subgraph Services["Service Layer (app/services/)"]
        AttMgr["AttendanceManager + VisionTracker"]
        QuizMgr["QuizSessionManager + TimedTokenManager"]
        PollSvc["poll_service"]
        AISvc["AIServiceAgent"]
        WSMgr["ConnectionManager (ws_manager)"]
    end

    subgraph Storage["Data & External Services"]
        DB["SQLite (data/smartclass.db, WAL)"]
        Files["uploads/ & reports/"]
        CV["YOLOv8n + ByteTrack + OpenCV"]
        ExtAI["OpenAI API / faster-whisper / ffmpeg / git"]
    end

    Login --> ApiJS
    Lecturer --> ApiJS
    Lecturer --> WsJS
    Student --> ApiJS
    Student --> WsJS
    Forum --> ApiJS
    Forum --> WsJS

    ApiJS -->|REST / FormData| Main
    ApiJS --> R_Att
    ApiJS --> R_Quiz
    ApiJS --> R_Poll
    ApiJS --> R_Forum
    ApiJS --> R_Course
    ApiJS --> R_AI
    WsJS <-->|WebSocket| R_WS

    R_Att --> AttMgr
    R_Quiz --> QuizMgr
    R_Poll --> PollSvc
    R_Forum --> WSMgr
    R_AI --> AISvc
    R_WS --> WSMgr

    AttMgr --> DB
    AttMgr --> Files
    AttMgr --> CV
    QuizMgr --> DB
    PollSvc --> DB
    AISvc --> DB
    AISvc --> ExtAI
    Main --> DB
    R_Course --> DB
    R_Forum --> DB
```

---

## 2. Component Responsibilities & Interfaces

| Component | File | Responsibility | Key Interfaces |
| :--- | :--- | :--- | :--- |
| **Frontend Controllers** | `static/js/*.js` | Role guards, DOM updates, offline queue (`localStorage`), Chart.js/QRCode.js | Calls `api.*` in `api.js`; subscribes via `SmartClassSocket` |
| **Main App & Auth** | `app/main.py` | Lifespan DB init + seeding, page routes, `/api/auth/login`, `/api/sessions` | `health_check`, `login_or_register`, `get_session_report` |
| **Attendance Router & Manager** | `app/routers/attendance.py`, `attendance_service.py` | Frame/video ingestion, photo counting, self check-in QR, CSV/XLSX export | `process_frame`, `count_photo_with_boxes`, `trigger_checkin`, `export_to_xlsx` |
| **Quiz Router & Manager** | `app/routers/quiz.py`, `quiz_service.py` | `.xlsx` bank import, 300s token issuance & validation, track linking | `load_questions_from_excel`, `trigger_question`, `submit_answer` |
| **Polls Router & Service** | `app/routers/polls.py`, `poll_service.py` | Create, tally, vote, and close 2–4 option polls | `create_poll`, `submit_vote`, `close_poll` |
| **Courses & Forum Routers** | `app/routers/courses.py`, `forum.py` | Course catalog, enrollment approval, roster import, course forum, private inbox | `list_courses`, `import_course_students`, `create_course_post`, `mark_post_as_read` |
| **AI Router & Agent** | `app/routers/ai.py`, `ai_service.py` | `.vtt`/`.srt`/Whisper transcription, chunked summaries, GitHub clone + TF-IDF review | `summarize_lecture`, `review_homework` |
| **WebSocket Manager** | `app/services/ws_manager.py`, `routers/ws.py` | In-memory socket registry by `session_id` / `course:{id}` / `global` | `connect`, `disconnect`, `broadcast_event` |
