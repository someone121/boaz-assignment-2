# SmartClass AI - Comprehensive Technical Blueprint & Specification

**Course:** Introduction to Software Engineering (Ex2)  
**Authors:** Ron Perelman (212418735), Shlomo Tousieh Cohen (331294710)  
**Target Repository:** `someone121/boaz-assignment-1`

---

## 1. Technical Tools Evaluation & Benchmark Report (To-Do #3)

| Component / Task | Tool Selected | Alternatives Evaluated | Rationale & Practical In-Class Validation |
| :--- | :--- | :--- | :--- |
| **Object Detection** | **YOLOv8n (Nano)** | YOLOv5, Haar Cascades, MediaPipe | Runs at $\ge 25\text{ FPS}$ on standard laptop CPU. Excellent detection of occluded students across tiered classroom seating. |
| **Multi-Object Tracking** | **ByteTrack** | DeepSORT, SORT | ByteTrack maintains student identity trajectories (`track_id`) using low-score bounding box association without requiring heavy GPU Re-ID models. |
| **Backend Framework** | **FastAPI (Python)** | Flask, Django, Node.js Express | Async performance, native OpenAPI / Swagger documentation, and first-class integration with PyTorch/OpenCV. |
| **Database Engine** | **SQLite (via SQLAlchemy)** | PostgreSQL, MongoDB, JSON | Zero setup overhead, serverless single-file storage (`smartclass.db`), ACID compliant, and easily packaged for live demos. |
| **Frontend UI (Lecturer & Student)** | **Vanilla HTML5 + Tailwind CSS + Alpine.js** | React, Vue, Streamlit | Zero build steps (no `npm run build`), fast hot-reloading, extremely lightweight for mobile browsers via QR scan (**KISS**). |
| **Questionnaire Parser** | **openpyxl / pandas** | Custom CSV Parser | Robust handling of pre-made Excel sheets (`.xlsx`) with questions, options, and answer keys. |
| **LLM Orchestration** | **LiteLLM / OpenAI API / LangChain** | Local HuggingFace transformers | Instant integration with existing LLM APIs for video lecture transcripts and repository homework reviews without requiring local CUDA hardware. |

---

## 2. Statement of Work (SoW) (To-Do #4)

### 2.1 Project Goal & Deliverables
To deliver a functional web-based teaching tool demonstrating 5 integrated features:
1. Automated video/image person counting and continuous dwell-time tracking with Excel export.
2. 5-minute time-gated QR questions loaded from an Excel file.
3. Rapid in-class instant polling.
4. AI lecture summary extraction from recording transcripts.
5. AI homework review and cross-student comparison.

### 2.2 Scope & Boundaries
* **In Scope:** Standalone local web server, local camera/video processing, dynamic QR generation, mobile-responsive web form, mock/API LLM integration.
* **Out of Scope:** Direct API integration with university SSO (Moodle/מידע אישי) or live Zoom cloud webhooks (as explicitly stated in the guidelines).

---

## 3. Client Stories & Detailed Use Cases (To-Do #6)

### Use Case 1: Continuous Attendance Tracking
* **Actor:** Lecturer
* **Precondition:** Camera is pointed at the classroom or a sample room video is loaded.
* **Flow:**
  1. Lecturer clicks **"Start Session"** on the dashboard.
  2. The server continuously or periodically processes frames using YOLOv8 + ByteTrack.
  3. Every active `track_id` accumulates dwell seconds.
  4. At session end, the lecturer clicks **"Export Attendance"**.
  5. The server calculates $\text{Presence Ratio} = \frac{\text{Tracked Seconds}}{\text{Total Session Seconds}}$ and downloads `attendance_report.xlsx`.

### Use Case 2: 5-Minute Timed In-Class Quiz
* **Actor:** Lecturer & Student
* **Precondition:** Lecturer uploaded an Excel question bank before class.
* **Flow:**
  1. Lecturer selects **"Trigger Question #1"** on the dashboard.
  2. The server activates a question instance and generates a dynamic QR code containing a secure token valid for $T = 300\text{ seconds}$ (5 minutes).
  3. The QR code is projected on the classroom screen.
  4. Students scan the QR code using their smartphone browser.
  5. The browser displays a simple mobile web form (Student ID, Name, Answer Option).
  6. If submitted within 5 minutes, the server stores the submission and increments the live response counter.
  7. At $t > 300\text{ seconds}$, the token expires and subsequent submissions are blocked with an HTTP 403 error.

### Use Case 3: Instant KISS Poll
* **Actor:** Lecturer & Student
* **Flow:**
  1. Lecturer types a question (e.g., "Do you follow this step?") or clicks a default True/False poll.
  2. Live voting opens instantly; students vote with 1 tap.
  3. Results appear on the lecturer dashboard in a dynamic bar chart.

### Use Case 4 & 5: AI Lecture Summary & Homework Review
* **Actor:** Lecturer / Teaching Assistant
* **Flow (Summary):** Lecturer uploads lecture video or transcript; LLM agent outputs a structured brief: Key Concepts, Code Examples, and FAQ.
* **Flow (Review):** Lecturer uploads student project repositories; LLM agent reviews code design (SOLID principles, clean architecture) and generates cross-student comparative notes.

---

## 4. Database Schema (SQLite / Relational Design)

```sql
-- Students Registry
CREATE TABLE students (
    student_id VARCHAR(20) PRIMARY KEY,
    full_name VARCHAR(100) NOT NULL,
    email VARCHAR(100)
);

-- Lecture Sessions
CREATE TABLE sessions (
    id VARCHAR(36) PRIMARY KEY,
    course_name VARCHAR(100) NOT NULL,
    start_time TIMESTAMP NOT NULL,
    end_time TIMESTAMP,
    total_duration_minutes INT DEFAULT 0
);

-- Visual Attendance Tracking Logs
CREATE TABLE attendance_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(36) NOT NULL,
    track_id INT NOT NULL,
    student_id VARCHAR(20),
    dwell_seconds INT DEFAULT 0,
    is_eligible BOOLEAN DEFAULT FALSE,
    FOREIGN KEY(session_id) REFERENCES sessions(id),
    FOREIGN KEY(student_id) REFERENCES students(student_id)
);

-- Questions Pool (Imported from Excel)
CREATE TABLE quiz_questions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    question_text TEXT NOT NULL,
    option_a VARCHAR(255) NOT NULL,
    option_b VARCHAR(255) NOT NULL,
    option_c VARCHAR(255),
    option_d VARCHAR(255),
    correct_option VARCHAR(2) NOT NULL
);

-- Timed Active Question Tokens (5-Minute Window)
CREATE TABLE active_question_tokens (
    token VARCHAR(64) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    question_id INT NOT NULL,
    created_at TIMESTAMP NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    FOREIGN KEY(session_id) REFERENCES sessions(id),
    FOREIGN KEY(question_id) REFERENCES quiz_questions(id)
);

-- Student Answers
CREATE TABLE quiz_submissions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    token VARCHAR(64) NOT NULL,
    student_id VARCHAR(20) NOT NULL,
    selected_option VARCHAR(2) NOT NULL,
    submitted_at TIMESTAMP NOT NULL,
    is_correct BOOLEAN NOT NULL,
    FOREIGN KEY(token) REFERENCES active_question_tokens(token)
);

-- Instant Polls
CREATE TABLE polls (
    id VARCHAR(36) PRIMARY KEY,
    session_id VARCHAR(36) NOT NULL,
    prompt TEXT NOT NULL,
    option_1 VARCHAR(100) NOT NULL,
    option_2 VARCHAR(100) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    is_open BOOLEAN DEFAULT TRUE
);
```

---

## 5. Software Architecture & Class Diagram (To-Do #7 & #8)

### 5.1 Object-Oriented Architecture (OOD Principles Applied)
- **Single Responsibility (SRP):** Vision tracking, question timing, and data exporting reside in distinct services.
- **Open/Closed (OCP) & Strategy Pattern:** Attendance criteria implemented through `PresencePolicy` interface.
- **Dependency Inversion (DIP):** Database access mediated via repositories.

```
                    ┌─────────────────────────┐
                    │      FastAPI Router     │
                    └────────────┬────────────┘
                                 │
         ┌───────────────────────┼────────────────────────┐
         ▼                       ▼                        ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│ AttendanceEngine │    │  QuizCoordinator │    │  AIServiceAgent  │
└────────┬─────────┘    └────────┬─────────┘    └────────┬─────────┘
         │                       │                       │
         ▼                       ▼                       ▼
┌──────────────────┐    ┌──────────────────┐    ┌──────────────────┐
│  VisionTracker   │    │  TokenValidator  │    │  LLMClientBridge │
│  (YOLO + Byte)   │    │  (5-Min Expiry)  │    │  (Summarizer/Rev)│
└────────┬─────────┘    └────────┬─────────┘    └──────────────────┘
         │                       │
         ▼                       ▼
┌──────────────────────────────────────────────────────────────────┐
│                      Repository Layer (SQLite)                   │
└──────────────────────────────────────────────────────────────────┘
```

### 5.2 Python Class Definitions Outline
```python
from abc import ABC, abstractmethod
from datetime import datetime, timedelta
from typing import Dict, List, Optional

class PresencePolicy(ABC):
    @abstractmethod
    def evaluate(self, dwell_seconds: int, session_total_seconds: int) -> bool:
        pass

class PercentagePresencePolicy(PresencePolicy):
    def __init__(self, required_ratio: float = 0.70):
        self.required_ratio = required_ratio

    def evaluate(self, dwell_seconds: int, session_total_seconds: int) -> bool:
        if session_total_seconds == 0:
            return False
        return (dwell_seconds / session_total_seconds) >= self.required_ratio

class TrackedPerson:
    def __init__(self, track_id: int):
        self.track_id = track_id
        self.first_seen = datetime.now()
        self.last_seen = datetime.now()
        self.total_dwell_seconds = 0
        self.student_id: Optional[str] = None

    def update_presence(self, elapsed_seconds: int):
        self.last_seen = datetime.now()
        self.total_dwell_seconds += elapsed_seconds

class AttendanceManager:
    def __init__(self, policy: PresencePolicy):
        self.policy = policy
        self.active_tracks: Dict[int, TrackedPerson] = {}
        self.session_start = datetime.now()

    def register_detections(self, detected_track_ids: List[int], interval_seconds: int):
        for t_id in detected_track_ids:
            if t_id not in self.active_tracks:
                self.active_tracks[t_id] = TrackedPerson(track_id=t_id)
            self.active_tracks[t_id].update_presence(interval_seconds)

    def generate_report(self) -> List[dict]:
        total_session_seconds = (datetime.now() - self.session_start).total_seconds()
        report = []
        for track in self.active_tracks.values():
            report.append({
                "track_id": track.track_id,
                "student_id": track.student_id or "Unassigned",
                "dwell_minutes": round(track.total_dwell_seconds / 60, 2),
                "is_present": self.policy.evaluate(track.total_dwell_seconds, int(total_session_seconds))
            })
        return report

class TimedTokenManager:
    def __init__(self, ttl_minutes: int = 5):
        self.ttl = timedelta(minutes=ttl_minutes)

    def create_token(self, question_id: int) -> dict:
        now = datetime.now()
        return {
            "token": f"token_{question_id}_{int(now.timestamp())}",
            "question_id": question_id,
            "created_at": now,
            "expires_at": now + self.ttl
        }

    def is_valid(self, token_info: dict) -> bool:
        return datetime.now() <= token_info["expires_at"]
```

---

## 6. End-to-End API Specifications (REST Endpoints)

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `POST` | `/api/session/start` | Creates a new lecture session. |
| `POST` | `/api/attendance/frame` | Ingests a camera frame, runs YOLO + tracker, updates dwell times. |
| `GET` | `/api/attendance/export` | Downloads the compiled Excel attendance spreadsheet. |
| `POST` | `/api/quiz/upload-excel` | Ingests `.xlsx` question bank. |
| `POST` | `/api/quiz/trigger` | Activates a question; returns dynamic QR URL and 300s expiring token. |
| `POST` | `/api/quiz/submit` | Student mobile submit endpoint; enforces 5-minute validity check. |
| `POST` | `/api/poll/create` | Broadcasts an on-the-spot KISS poll. |
| `POST` | `/api/poll/vote` | Submits a vote for an active poll. |
| `POST` | `/api/ai/summarize-lecture` | Uploads transcript/audio for LLM summary generation. |
| `POST` | `/api/ai/review-homework` | Submits repository links for automated comparative code review. |
| `PATCH` | `/api/courses/{course_id}/lecturer` | Reassigns a course to another existing lecturer. Body: `{ acting_lecturer_id, lecturer_id }`. Only lecturers may call it. |
| `GET` | `/api/courses/{course_id}/posts?user_id=…` | Course forum threads with nested replies. Only the course's lecturer or approved students. |
| `POST` | `/api/courses/{course_id}/posts` | Creates a forum thread. Body: `{ author_id, title, content }`. |
| `POST` | `/api/posts/{post_id}/comments` | Replies to a thread. Body: `{ author_id, content }`. |

Course forum access is checked on the server: the caller's role is looked up in the `users` table (never taken from the request), lecturers must match `courses.lecturer_id`, and students need an `approved` row in `enrollments`. Otherwise the response is `403`.

---

## 7. Testing Strategy & Quality Assurance (To-Do #9)

### 7.1 Unit Tests (pytest)
- **Presence Policy Tests:**
  - `test_presence_eligible()`: Verifies student with $\ge 70\%$ duration is flagged `Present`.
  - `test_presence_below_threshold()`: Verifies student with $69.9\%$ duration is flagged `Absent`.
- **Token Expiry Tests:**
  - `test_token_valid_at_299_seconds()`: Returns `True`.
  - `test_token_invalid_at_301_seconds()`: Returns `False`.
- **Excel Parser Tests:**
  - Verify ingestion of sample quiz sheet (`questions.xlsx`) and correct mapping of keys.

### 7.2 Integration Tests
- **Vision Pipeline to Attendance:** Stream simulated video frames into `AttendanceManager` and assert accurate accumulation of `total_dwell_seconds` per `track_id`.
- **Concurrency Test:** Simulate 40 simultaneous student submissions against `/api/quiz/submit` within 5 seconds to ensure SQLite transactional integrity without table locks.

### 7.3 In-Class Demo Validation (Acceptance Criteria)
1. Point webcam at students or load the official Ex2 classroom image.
2. Confirm YOLOv8 correctly detects and bounds people in the frame.
3. Trigger Question #1 on screen, scan QR with smartphone, answer, and observe immediate dashboard count increment.
4. Export and inspect the generated Excel file.