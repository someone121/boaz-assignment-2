# Software Requirements Specification (SRS)

## SmartClass AI - Next Generation Classroom Management & Learning Tool

**Version:** 1.0.0

**Date:** November 2026

**Authors:** Ron Perelman & Shlomo Tousieh Cohen

**Course:** Introduction to Software Engineering (Ex2)

## 1. Introduction

### 1.1 Purpose

This document specifies the software requirements for **SmartClass AI**, a KISS-oriented web application designed to automate physical classroom attendance tracking, enable frictionless student interaction via temporary QR tokens, and leverage LLMs for lecture summarization and assignment reviews.

### 1.2 Scope

The application operates as an internal server-first system. It removes the need for native mobile applications by providing a lightweight mobile web client for students and an operational dashboard for lecturers. It interfaces with computer vision models for human tracking and LLM APIs for text analysis.

## 2. Overall Description

### 2.1 User Personas

* **Lecturer / TA:** Launches class sessions, initiates computer vision tracking, triggers 5-minute quiz challenges, creates instant polls, uploads recordings, and downloads attendance spreadsheets.

* **Student:** Connects via mobile browser to register answers to timed questions, submits poll feedback, and views homework evaluations.

### 2.2 System Operating Environment

* **Server:** Python 3.10+, FastAPI framework, SQLite storage.

* **Hardware Integration:** Standard USB/built-in web camera or RTSP stream.

* **Clients:** Standard compliant web browsers (Chrome, Safari, Firefox) on desktop and mobile.

## 3. Specific Requirements & Use Cases

### 3.1 Functional Requirements

#### Feature 1: Automated Visual Attendance & Dwell-Time Calculation

* **FR-1.1:** The server shall consume frames from a classroom camera or uploaded batch photo.

* **FR-1.2:** The server shall run YOLOv8 to locate bounding boxes of students in the room.

* **FR-1.3:** The server shall maintain unique track IDs across frames using ByteTrack.

* **FR-1.4:** The system shall compute total active presence duration for each detected individual.

* **FR-1.5:** The system shall export an attendance report in CSV/Excel format containing: Student ID, Name, Total Minutes Observed, and Presence Status (`Present` if duration $\ge 70\%$, otherwise `Absent`/`Partial`).

#### Feature 2: 5-Minute Excel-Based In-Class Interaction

* **FR-2.1:** The instructor can upload an Excel workbook (`.xlsx`) containing multiple-choice or True/False questions.

* **FR-2.2:** When a question is triggered, the system generates a dynamic QR code embedding a cryptographically signed token valid for exactly **300 seconds (5 minutes)**.

* **FR-2.3:** Submissions received after the 300-second window shall be rejected automatically.

* **FR-2.4:** Student responses are correlated with the active attendance session to provide dual-factor verification.

#### Feature 3: KISS Real-Time Polling

* **FR-3.1:** The instructor can broadcast a lightweight poll (single question, 2-4 options) with one click.

* **FR-3.2:** Student responses update the lecturer's dashboard in real-time.

#### Feature 4: ML Video Lecture Summarizer

* **FR-4.1:** The system shall accept recorded video/audio files (`.mp4`, `.m4a`).

* **FR-4.2:** The backend processes audio transcription and feeds the transcript to an LLM prompt pipeline.

* **FR-4.3:** The system generates a structured summary with: Main Concepts, Time-indexed Topics, and Follow-up Discussion points.

#### Feature 5: Homework LLM Comparative Review

* **FR-5.1:** The system accepts student repository links or uploaded source files.

* **FR-5.2:** The AI evaluator assesses architectural design (OOD principles, cohesion, coupling) and scores each assignment.

* **FR-5.3:** The system generates comparative feedback identifying common anti-patterns across multiple submissions.

## 4. Software Design & Architecture

### 4.1 Component Diagram (High-Level)

```
+-----------------------------------------------------------------+
|                       Presentation Layer                        |
|  +---------------------------+   +---------------------------+  |
|  | Lecturer Dashboard (Web)  |   | Student Mobile Web Client |  |
|  +-------------+-------------+   +-------------+-------------+  |
+----------------|-------------------------------|----------------+
                 | (REST / WebSocket)            | (HTTP POST / QR)
+----------------v-------------------------------v----------------+
|                        API Gateway / FastAPI                    |
+-----------------------------------------------------------------+
|                         Service Layer                           |
|  +-----------------------+    +------------------------------+  |
|  | AttendanceService     |    | QuizPollService              |  |
|  | - YOLO Detection      |    | - Excel Question Loader      |  |
|  | - ByteTrack Tracker   |    | - 5-Min Token Manager        |  |
|  | - Face Identifier     |    | - Real-time Aggregator       |  |
|  +-----------+-----------+    +--------------+---------------+  |
|              |                               |                  |
|  +-----------v-----------+    +--------------v---------------+  |
|  | SummaryService (LLM)  |    | AssignmentReviewerService    |  |
|  +-----------------------+    +------------------------------+  |
+-----------------------------------------------------------------+
|                         Data Layer                              |
|  +-----------------------------------------------------------+  |
|  | SQLite Repository (Students, Sessions, Quizzes, Logs)     |  |
|  +-----------------------------------------------------------+  |
+-----------------------------------------------------------------+

```

### 4.2 Low-Level Class Diagram (OOP Design)

```
┌─────────────────────────────────────────────────────────────┐
│                      AttendanceManager                      │
├─────────────────────────────────────────────────────────────┤
│ - tracker: TrackerService                                   │
│ - presencePolicy: PresencePolicy                            │
│ - activeSessions: Map<String, ClassroomSession>             │
├─────────────────────────────────────────────────────────────┤
│ + processFrame(frameData: bytes): FrameResult               │
│ + evaluateAttendance(sessionId: String): AttendanceReport   │
│ + exportToSpreadsheet(sessionId: String): File              │
└──────────────────────────────┬──────────────────────────────┘
                               │ uses
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     PresencePolicy (Interface)              │
├─────────────────────────────────────────────────────────────┤
│ + isEligible(trackedMinutes: int, sessionTotal: int): bool  │
└──────────────────────────────┬──────────────────────────────┘
                               ▲
              ┌────────────────┴────────────────┐
              │                                 │
┌─────────────┴────────────────┐  ┌─────────────┴─────────────┐
│  PercentagePresencePolicy    │  │  FixedTimePresencePolicy  │
├──────────────────────────────┤  ├───────────────────────────┤
│ - thresholdRatio: float = 0.7│  │ - requiredMinutes: int = 45│
├──────────────────────────────┤  ├───────────────────────────┤
│ + isEligible(...)            │  │ + isEligible(...)         │
└──────────────────────────────┘  └───────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      QuizSessionManager                     │
├─────────────────────────────────────────────────────────────┤
│ - activeToken: String                                       │
│ - expiresAt: DateTime                                       │
│ - questionsPool: List<Question>                             │
├─────────────────────────────────────────────────────────────┤
│ + loadQuestionsFromExcel(filePath: String): void            │
│ + triggerQuestion(index: int, durationMinutes: int = 5): QR │
│ + submitAnswer(studentId: String, answer: String): bool     │
│ + isExpired(): bool                                         │
└─────────────────────────────────────────────────────────────┘

```

### 4.3 Sequence Diagram: 5-Minute Verification & Attendance Linkage

```
Student Mobile            Lecturer Dashboard             Server API                Database
      │                           │                          │                         │
      │                           │── Trigger Question 1 ───>│                         │
      │                           │   (5-minute duration)    │── Store Expiring Token ─>│
      │                           │<─ Return Dynamic QR ─────│                         │
      │                           │                          │                         │
      │     [Displays QR on projector screen]                │                         │
      │                           │                          │                         │
      │── Scan QR & Submit Answer ──────────────────────────>│                         │
      │   (StudentID + Token)     │                          │── Verify Token Expiry ──>│
      │                           │                          │   (Timestamp <= 5 min)  │
      │                           │                          │                         │
      │                           │                          │── Log Answer & Match ──>│
      │                           │                          │   With Visual Tracker   │
      │<── 200 OK (Confirmed) ────│                          │                         │
      │                           │<─ Live Count Update ─────│                         │

```

## 5. Non-Functional Requirements

1. **Performance:** Single frame inference for bounding box extraction shall not exceed 300ms on a modern CPU.

2. **KISS Usability:** Student interaction shall require zero authentication setup; accessing the web form takes $\le 2$ clicks after scanning the QR.

3. **Security:** Tokens generated for questionnaires must expire strictly after 300 seconds to prevent link sharing outside the classroom.

4. **Data Privacy:** Facial image files are processed in-memory and discarded; only derived numeric embeddings and presence timestamps are persisted.

## 6. Testing Strategy

1. **Unit Testing:**

   * Test `PresencePolicy` boundary cases (e.g., student present 69% vs 70% of duration).

   * Test `QuizSessionManager` token expiry validation (submission at 299s accepted, at 301s rejected).

   * Test Excel parser against valid and corrupted `.xlsx` schemas.

2. **Integration Testing:**

   * Simulate camera frame feeds through OpenCV capture into tracking pipeline.

   * Verify simultaneous mobile submissions under concurrent load (50 students submitting answers in a 10-second window).

3. **Acceptance Testing:**

   * Execute in-class live demo with the provided sample classroom photograph and verify person count accuracy against known student ground truth.