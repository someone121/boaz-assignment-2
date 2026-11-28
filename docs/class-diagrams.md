# Class Diagrams & Design Patterns

## 1. Domain Services & Strategy Pattern

```mermaid
classDiagram
    class PresencePolicy {
        <<abstract>>
        +is_eligible(dwell_seconds: int, session_total_seconds: int) bool
    }

    class PercentagePresencePolicy {
        +threshold_ratio: float
        +is_eligible(dwell_seconds: int, session_total_seconds: int) bool
    }

    class FixedTimePresencePolicy {
        +required_seconds: int
        +is_eligible(dwell_seconds: int, session_total_seconds: int) bool
    }

    class TrackedPerson {
        +track_id: int
        +first_seen: datetime
        +last_seen: datetime
        +total_dwell_seconds: int
        +student_id: Optional~str~
        +update_presence(elapsed_seconds: int) void
    }

    class VisionTracker {
        +model_name: str
        +mode: str
        +is_video(filename: str) bool
        +detect_tracks(frame_bytes: bytes, filename: str) list~int~
        +detect_video_tracks(video_bytes: bytes, filename: str, sample_every_seconds: int) dict
        +count_photo_with_boxes(image_bytes: bytes, filename: str) dict
    }

    class AttendanceManager {
        +policy: PresencePolicy
        +tracker: VisionTracker
        +active_sessions: dict
        +process_frame(db, session_id, frame_bytes, filename, interval_seconds) dict
        +trigger_checkin(db, session_id, lecturer_id, ttl_seconds) dict
        +submit_checkin(db, token, student_id, full_name) dict
        +evaluate_attendance(db, session_id) list~dict~
        +stop_session(db, session_id) dict
        +export_to_csv(db, session_id) Path
        +export_to_xlsx(db, session_id) Path
    }

    PresencePolicy <|-- PercentagePresencePolicy
    PresencePolicy <|-- FixedTimePresencePolicy
    AttendanceManager o-- PresencePolicy
    AttendanceManager *-- VisionTracker
    AttendanceManager *-- TrackedPerson
```

---

## 2. Quiz, AI & WebSocket Managers

```mermaid
classDiagram
    class TimedTokenManager {
        +ttl: timedelta
        +build_token_record(session_id, question_id, lecturer_id, now) ActiveQuestionToken
        +is_valid(token_row, now) bool
    }

    class QuizSessionManager {
        +token_manager: TimedTokenManager
        +load_questions_from_excel(db, file_path, session_id) list~QuizQuestion~
        +trigger_question(db, session_id, question_id, lecturer_id) dict
        +get_token_question(db, token) dict
        +submit_answer(db, token, student_id, full_name, selected_option) dict
    }

    class AIServiceAgent {
        +parse_subtitle_transcript(raw_text: str) str
        +extract_transcript(filename: str, file_path: Path) tuple
        +summarize_lecture(db, filename, file_path, session_id, course_name, course_id) tuple
        +review_homework(db, repo_urls, session_id, student_id) list~HomeworkReview~
    }

    class ConnectionManager {
        +active_connections: dict
        +connect(websocket, session_id) void
        +disconnect(websocket, session_id) void
        +broadcast_event(session_id, event, data) void
    }

    QuizSessionManager *-- TimedTokenManager
    QuizSessionManager ..> AttendanceManager : links student track
```

---

## 3. SQLAlchemy ORM Models

```mermaid
classDiagram
    class User {
        +user_id: str
        +full_name: str
        +role: str
        +password_hash: str
        +is_approved: bool
    }
    class Student {
        +student_id: str
        +full_name: str
    }
    class Course {
        +id: str
        +name: str
        +lecturer_id: str
    }
    class Enrollment {
        +id: int
        +student_id: str
        +course_id: str
        +status: str
    }
    class LectureSession {
        +id: str
        +course_name: str
        +course_id: str
        +total_detected: int
        +students_left_early: int
        +is_active: bool
    }
    class AttendanceRecord {
        +id: int
        +session_id: str
        +track_id: int
        +student_id: str
        +dwell_seconds: int
        +is_eligible: bool
    }
    class AttendanceCheckIn {
        +id: int
        +session_id: str
        +student_id: str
        +student_name: str
        +checked_in_at: datetime
    }
    class Poll {
        +id: str
        +session_id: str
        +prompt: str
        +is_open: bool
    }
    class ForumPost {
        +id: int
        +course_id: str
        +post_type: str
        +title: str
        +content: str
        +is_read: bool
    }
    class ForumComment {
        +id: int
        +post_id: int
        +author_id: str
        +content: str
    }

    Course "1" --> "*" Enrollment
    Student "1" --> "*" Enrollment
    LectureSession "1" --> "*" AttendanceRecord
    LectureSession "1" --> "*" AttendanceCheckIn
    LectureSession "1" --> "*" Poll
    ForumPost "1" --> "*" ForumComment
```

---

## 4. Design Patterns Applied

1. **Strategy Pattern:** `PresencePolicy` (`PercentagePresencePolicy`, `FixedTimePresencePolicy`) decouples attendance eligibility rules from `AttendanceManager`.
2. **Singleton / Process-Scoped Manager:** Module-level `attendance_manager`, `quiz_manager`, `ai_service`, and `ws_manager` hold shared in-memory state within the single Uvicorn worker.
3. **Fallback / Graceful Degradation:** `VisionTracker` falls back to mock tracking only when YOLO/OpenCV cannot load; `AIServiceAgent` falls back from OpenAI/Whisper to `faster-whisper` or explicitly labelled `[Non-LLM Static Analysis]` / `Transcription Unavailable`.
4. **Observer (Pub/Sub) via WebSocket:** `ConnectionManager` broadcasts domain events (`QUIZ_UPDATE`, `POLL_UPDATE`, `FORUM_THREAD_NEW`, `FORUM_COMMENT_NEW`, `STUDENT_MESSAGE_NEW`, `ATTENDANCE_UPDATE`, `ATTENDANCE_DONE`, `SUMMARY_READY`) to subscribed browser clients.
5. **Service Layer Separation:** Routers handle HTTP/validation only and delegate persistence & business rules to `app/services/`.
