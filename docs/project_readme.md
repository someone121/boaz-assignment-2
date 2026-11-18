# SmartClass AI - Modern Teaching & Classroom Analytics Platform

**Course:** Introduction to Software Engineering (OOP / OOD) - Ex2  
**Institution:** Ariel University  
**Authors:**
- Ron Perelman (ID: 212418735)
- Shlomo Tousieh Cohen (ID: 331294710)
- **Repository:** [https://github.com/someone121/boaz-assignment-1](https://github.com/someone121/boaz-assignment-1)

---

## 1. Problem Statement

Current digital teaching tools used in academic classrooms create high cognitive friction:
- Roll-call and attendance tracking waste 5–15 minutes of lecture time or rely on easily faked single-action sign-ins (students signing in on a tablet or QR code and leaving immediately).
- Passive listening limits real-time student engagement and understanding checks.
- Ad-hoc lecture summaries and deep homework peer evaluations are tedious, slow, and unstandardized.

**SmartClass AI** addresses this challenge through a lightweight, web-based software suite focusing on the **KISS** principle (Keep It Simple, Stupid). It combines real-time computer vision presence verification with modern LLM workflows to maximize active learning while minimizing instructor overhead.

---

## 2. Core Features

1. **Continuous Visual Attendance (Primary Feature):**
   - Panoramic classroom video stream processed on the server using **YOLOv8** for human detection and **ByteTrack** for persistent spatial tracking.
   - Initial facial embedding matching (FaceNet/ArcFace) maps tracks to enrolled students.
   - Calculates actual dwell time (time spent in seat).
   - Generates downloadable CSV / Excel spreadsheets containing total presence duration and attendance status based on predefined configurable thresholds.

2. **5-Minute Timed Engagement & Real-Time Feedback:**
   - Instructors upload a structured questions file (Excel/CSV) prior to class.
   - The instructor triggers a question during lecture; the server displays a dynamic QR code valid for exactly **5 minutes**.
   - Students scan using their phone browser (no app installation required) to answer single-choice or true/false questions and raise suggestions.

3. **On-The-Spot "KISS" Live Polls:**
   - 1-click generation of interactive polls during class to gauge real-time understanding.
   - Live visual aggregation displayed to the lecturer.

4. **Automated ML Class Video Summarizer:**
   - Processes recorded lectures (Zoom / Google Meet MP4 or M4A).
   - Transcribes audio and utilizes an LLM agent to extract key definitions, timestamps, and actionable lecture summaries.

5. **AI-Driven Homework Evaluation & Peer Cross-Review:**
   - Ingests student repository submissions and compares code design, SOLID compliance, and complexity.
   - Produces individual rubric-based critique and cross-student comparative insights.

---

## 3. System Architecture & Tech Stack

```text
┌─────────────────────────────────────────────────────────────┐
│                       Client Layer                          │
│  - Lecturer Web Dashboard (React / Vanilla JS Desktop)      │
│  - Student Mobile Web Interface (KISS Responsive Browser)   │
└──────────────┬──────────────────────────────┬───────────────┘
               │                              │
               ▼ (HTTP / WebSockets)          ▼ (QR Scan Token)
┌─────────────────────────────────────────────────────────────┐
│                    Application Server                       │
│  - Framework: FastAPI (Python 3.10+)                        │
│  - Vision Worker: OpenCV + YOLOv8 + ByteTrack               │
│  - LLM Orchestrator: LangChain / OpenAI API / Ollama        │
│  - Attendance Engine: Dwell-time accumulator                │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                     Data & File Storage                     │
│  - SQLite Database (Sessions, Students, Polls, Logs)        │
│  - Static Storage (Uploaded videos, spreadsheets, photos)   │
└─────────────────────────────────────────────────────────────┘
```

---

## 4. Quick Start & Demo Setup

### Prerequisites
- Python 3.10+
- Webcam or sample classroom video/photo

### Installation
```bash
# Clone the repository
git clone https://github.com/someone121/boaz-assignment-1.git
cd boaz-assignment-1

# Create and activate virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### Running the Application
```bash
# Launch server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```
- Open Lecturer Dashboard: `http://localhost:8000/dashboard`
- Student Interface: Scan the generated QR code or browse to `http://localhost:8000/live`

---

## 5. Live In-Class Demo Guide

1. **Run Attendance:** Point the camera at the audience or supply the sample classroom image provided in Ex2. Trigger detection and download the resulting `attendance_session.csv`.
2. **Launch 5-Minute Quiz:** Upload the provided sample Excel quiz (`questions_sample.xlsx`), trigger Question 1, scan the QR code via mobile phone, and show real-time response aggregation.
3. **Execute Poll:** Start a 10-second instant poll ("Understand current concept? Yes/No") and show immediate dashboard updates.
4. **Summary & Code Review Demo:** Inspect pre-computed outputs from the Lecture Summary agent and Homework evaluation agent.