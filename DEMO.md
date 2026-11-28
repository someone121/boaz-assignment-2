# SmartClass AI — 10-Minute In-Class Demo Script (`DEMO.md`)

This script walks through a live 10-minute classroom demonstration of **SmartClass AI** covering all five core features (**F1–F5**).

---

## Pre-Class Checklist (Run 5 Minutes Before Demo)

- [ ] **`OPENAI_API_KEY` set and tested:** Verify `.env` has a valid `OPENAI_API_KEY` if demonstrating live Whisper audio/video transcription and LLM rubric reviews (otherwise `.vtt`/`.srt`/`.txt` + `[Non-LLM Static Analysis]` work offline).
- [ ] **`PUBLIC_BASE_URL` set to your LAN IP:** Find your IPv4 address (`ipconfig` on Windows / `hostname -I` on Linux/macOS) and set `PUBLIC_BASE_URL=http://<LAN_IP>:8000` in `.env` before `docker compose up -d`. Then open the Lecturer Dashboard on **`http://localhost:8000/`** — this lets the browser webcam (`getUserMedia`) work on `localhost` while student QR codes point phones to `<LAN_IP>:8000`.
- [ ] **Firewall port `8000` open:** Ensure inbound TCP port `8000` is allowed on your local firewall for the classroom Wi-Fi profile.
- [ ] **Sample assets ready in `data/samples/`:**
  - Sample classroom photo (`.jpg`/`.png`) for **Count People in Class Photo**.
  - Sample `.vtt` (or `.srt`) transcript for **Lecture Summarizer**.
  - Sample `.xlsx` question bank (`Question | A | B | C | D | Correct`).
  - Text file with 2–3 public GitHub repository URLs for **Homework Review**.
- [ ] **Student phones on the same Wi-Fi:** Confirm at least one test phone can load `http://<LAN_IP>:8000/student_dashboard`.

---

## Pre-Demo Setup (2 minutes before class)

1. **Start the server on your laptop:**
   ```bash
   docker compose up --build -d
   # OR locally:
   # python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
   ```
2. **Find your LAN IP** (so student phones on the same Wi-Fi can scan QR codes):
   - Windows: `ipconfig` (look for IPv4 Address, e.g. `192.168.1.42`)
   - macOS/Linux: `hostname -I`
3. **Open the Lecturer Dashboard via LAN IP** (not `localhost`!):
   - Navigate to `http://<LAN_IP>:8000/`
   - Sign in as Lecturer: ID `111111111`, Password `admin123`
4. **Optional:** Seed the class roster in **Tab 4 → Import Student Roster** using a CSV/XLSX of student first names (no ID numbers needed).

---

## Live 10-Minute Demo Flow

### Minute 0–2: F1 Visual Attendance + Student Self Check-In
1. Click **+ Start Session** (e.g., `"I2SE Live Demo"`).
2. Open **Tab 3: Attendance Control**:
   - **Class Photo Count:** Upload one of the course classroom photos in **Count People in Class Photo** → show the bounding-box overlay and detected student count.
   - **Self Check-In QR:** Click **Show Check-In QR** → students scan with their phone camera, log in with any demo ID/name, and tap **"I'm Here"** → watch their row appear live in the **Tracked Dwell-Time Roster** (`source: self_checkin`).
   - *(Optional)* Click **Start Webcam Stream** to demonstrate continuous ByteTrack dwell-time accumulation.

### Minute 2–4: F3 Instant KISS Poll
1. Switch to **Tab 1: Live Quiz & Instant Polls**.
2. Click **Quick Yes/No** (`"Do you understand the current concept?"`) and click **Broadcast Live Poll**.
3. Students tap Yes/No on their phone → watch the `Chart.js` bar chart update live via WebSocket.
4. Click **Close Poll** → show the **"Poll Closed"** badge on the student view.

### Minute 4–6: F1/F2 5-Minute Timed QR Quiz
1. Upload a sample `.xlsx` question bank in **Tab 1** (`Question | A | B | C | D | Correct`).
2. Click **Launch Next Question** → project the 5-minute QR code (`05:00` countdown).
3. Students scan, pick an answer, and submit → watch the response counter and chart update live.

### Minute 6–8: F2 Real-Time Course Forum & Private Suggestions
1. Open `/forum` (in a second tab or student phone).
2. Post a thread or reply → show it appearing live on connected clients via WebSocket (`FORUM_THREAD_NEW` / `FORUM_COMMENT_NEW`).
3. Student sends a **Private Message to Lecturer** → switch to **Tab 4 → Student Messages / Suggestions** on the Lecturer Dashboard to see it arrive live and click **Mark as Read**.

### Minute 8–9: F4 Lecture Summary
1. Open **Tab 2: AI Video Summary & HW Review**.
2. Upload a `.vtt`/`.srt` transcript (or `.mp4` recording) → show the structured summary (Main Concepts & Topics, Key Definitions, Timeline, Open Questions, Review Exercises) and its automatic post in the Course Forum.

### Minute 9–10: F5 Homework Comparative Review + Spreadsheet Export
1. In **Tab 2 → AI Homework Comparative Review**, paste 2–3 GitHub repo URLs and click **Run Comparative OOD Evaluation** → show the 5-criterion rubric scores, cohort percentiles, and TF-IDF similarity check.
2. In **Tab 3**, click **End Session & Download CSV** and **Download .xlsx** → open the offline spreadsheet and the cozy **Session Report** modal.

---

## Fallback Plan (If Wi-Fi or Camera Fails)

| Issue | Fallback Action |
| :--- | :--- |
| **Classroom Wi-Fi blocks LAN port 8000** | Open two browser windows on the presenter laptop (`http://localhost:8000/lecturer_dashboard` and an incognito window at `http://localhost:8000/student_dashboard`), and copy-paste the QR URLs directly to demonstrate the exact same end-to-end flow. |
| **Laptop webcam unavailable / blocked** | Use **Count People in Class Photo** with a sample `.jpg` or upload a short `.mp4` clip via **Choose Frame / Video → Process**. |
| **No `OPENAI_API_KEY` or internet** | Lecture summary works offline with `.vtt`/`.srt`/`.txt` transcripts, and Homework Review automatically switches to `[Non-LLM Static Analysis]` + local TF-IDF similarity. |
| **Student device goes offline** | Posting a forum thread/reply or private message queues it in `localStorage` with a `Queued (offline)` badge and flushes automatically when back online. |
