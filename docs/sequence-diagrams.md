# Sequence Diagrams

## 1. Attendance via Photo / Webcam Frame / Video

```mermaid
sequenceDiagram
    actor Lecturer
    participant UI as "lecturer_dashboard.html"
    participant API as "routers/attendance.py"
    participant Mgr as "AttendanceManager"
    participant CV as "VisionTracker (YOLO+ByteTrack)"
    participant DB as "SQLite"

    Lecturer->>UI: Start Webcam / Upload Video or Photo
    UI->>API: POST /api/attendance/frame (session_id, file)
    API->>Mgr: process_frame(db, session_id, bytes)
    Mgr->>CV: detect_tracks() or detect_video_tracks()
    CV-->>Mgr: track_ids / appearance counts
    Mgr->>DB: Upsert AttendanceRecord (dwell_seconds, is_eligible)
    API-->>UI: {detected_count, detector_mode}
```

---

## 2. Student QR Self Check-In

```mermaid
sequenceDiagram
    actor Lecturer
    actor Student
    participant LUI as "lecturer.js"
    participant SUI as "student.js"
    participant API as "routers/attendance.py"
    participant WS as "ws_manager"
    participant DB as "SQLite"

    Lecturer->>LUI: Click "Show Check-In QR"
    LUI->>API: POST /api/attendance/checkin/trigger
    API->>DB: Insert ActiveCheckInToken (300s TTL)
    API-->>LUI: {token, qr_path: /checkin/{token}}
    Student->>SUI: Scan QR -> open /checkin/{token}
    SUI->>API: GET /api/attendance/checkin/{token}
    API-->>SUI: {course_name, seconds_remaining}
    Student->>SUI: Tap "I'm Here"
    SUI->>API: POST /api/attendance/checkin/submit
    API->>DB: Insert AttendanceCheckIn
    API->>WS: broadcast_event("ATTENDANCE_UPDATE")
    WS-->>LUI: Refresh live attendance table
```

---

## 3. Quiz Trigger, Scan, Submit & Live Chart Update

```mermaid
sequenceDiagram
    actor Lecturer
    actor Student
    participant LUI as "lecturer.js"
    participant SUI as "student.js"
    participant API as "routers/quiz.py"
    participant Mgr as "QuizSessionManager"
    participant WS as "ws_manager"
    participant DB as "SQLite"

    Lecturer->>LUI: Click "Launch Next Question"
    LUI->>API: POST /api/quiz/trigger
    API->>Mgr: trigger_question()
    Mgr->>DB: Save ActiveQuestionToken (expires_at = now + 300s)
    API-->>LUI: {token, qr_path: /s/{token}, remaining_questions}
    Student->>SUI: Scan QR -> /s/{token}
    SUI->>API: GET /api/quiz/token/{token}
    API-->>SUI: Question + options (or 410 Gone if expired)
    Student->>SUI: Select option & Submit
    SUI->>API: POST /api/quiz/submit
    API->>Mgr: submit_answer() (403 if > 300s)
    Mgr->>DB: Save QuizSubmission + link AttendanceRecord
    API->>WS: broadcast_event("QUIZ_UPDATE", counts)
    WS-->>LUI: Update Chart.js bars live
```

---

## 4. Instant Poll: Create, Vote & Close

```mermaid
sequenceDiagram
    actor Lecturer
    actor Student
    participant LUI as "lecturer.js"
    participant SUI as "student.js"
    participant API as "routers/polls.py"
    participant WS as "ws_manager"
    participant DB as "SQLite"

    Lecturer->>LUI: Broadcast Poll
    LUI->>API: POST /api/poll/create
    API->>DB: Insert Poll (is_open=True)
    API->>WS: broadcast_event("POLL_UPDATE")
    WS-->>SUI: Render 1-tap poll buttons
    Student->>SUI: Tap option
    SUI->>API: POST /api/poll/vote
    API->>DB: Insert PollVote
    API->>WS: broadcast_event("POLL_UPDATE", results)
    WS-->>LUI: Update Poll Chart.js
    Lecturer->>LUI: Click "Close Poll"
    LUI->>API: POST /api/poll/{id}/close
    API->>DB: Set is_open=False
    API->>WS: broadcast_event("POLL_UPDATE", is_open=False)
    WS-->>SUI: Disable buttons & show "Poll Closed"
```

---

## 5. Lecture Summary (Upload, Transcribe, Summarize & Forum)

```mermaid
sequenceDiagram
    actor Lecturer
    participant LUI as "lecturer.js"
    participant API as "routers/ai.py"
    participant AI as "AIServiceAgent"
    participant WS as "ws_manager"
    participant DB as "SQLite"

    Lecturer->>LUI: Upload .vtt / .srt / .mp4
    LUI->>API: POST /api/ai/summarize-lecture
    API->>AI: summarize_lecture()
    AI->>AI: Parse subtitles OR ffmpeg + Whisper / faster-whisper
    AI->>AI: Chunk transcript & generate 5-section summary
    AI->>DB: Save LectureSummary + ForumPost
    API->>WS: broadcast_event("SUMMARY_READY")
    API->>WS: broadcast_event("FORUM_THREAD_NEW" or "NEW_FORUM_POST")
    WS-->>LUI: Render formatted summary
```

---

## 6. Homework Review with Cohort Comparison

```mermaid
sequenceDiagram
    actor Lecturer
    participant LUI as "lecturer.js"
    participant API as "routers/ai.py"
    participant AI as "AIServiceAgent"
    participant Git as "GitHub (git clone --depth 1)"
    participant DB as "SQLite"

    Lecturer->>LUI: Submit repo URLs
    LUI->>API: POST /api/ai/review-homework
    API->>AI: review_homework(repo_urls)
    AI->>Git: Shallow clone each repo into TempDir
    Git-->>AI: README, file tree, source code
    AI->>AI: Score 5-criterion rubric (LLM or static metrics)
    AI->>AI: Compute TF-IDF cosine similarity & cohort percentiles
    AI->>DB: Persist HomeworkReview rows
    API-->>LUI: Cohort table, percentiles & similarity flags
```

---

## 7. Real-Time Course Forum Post & Offline Queue

```mermaid
sequenceDiagram
    actor Student
    participant FUI as "forum.js"
    participant LS as "localStorage Queue"
    participant API as "routers/forum.py"
    participant WS as "ws_manager"
    participant DB as "SQLite"

    Student->>FUI: Submit thread or reply
    alt Online
        FUI->>API: POST /api/courses/{id}/posts
        API->>DB: Insert ForumPost
        API->>WS: broadcast_event("FORUM_THREAD_NEW")
        WS-->>FUI: Prepend thread live on peers
    else Offline
        FUI->>LS: Save pending item & show "Queued (offline)"
        Note over FUI,LS: On window "online" or WS reconnect
        FUI->>API: Flush queued item
    end
```
