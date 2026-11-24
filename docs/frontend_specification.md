# Frontend Specification (KISS Web UI & Real-Time Client)

**Project:** SmartClass AI  
**Architecture Principle:** Zero-build, lightweight static frontend served directly by FastAPI (`/static`).

---

## 1. Frontend Tech Stack (CDN-Based)
- **Markup & Styling:** HTML5 + Tailwind CSS (via CDN `https://cdn.tailwindcss.com`).
- **Logic:** Vanilla JavaScript (ES6 Modules) — no React/Vue/Webpack build overhead.
- **HTTP Client:** **Axios** (`https://cdn.jsdelivr.net/npm/axios/dist/axios.min.js`) for all REST API operations (`FormData` file uploads, JSON payloads, binary CSV downloads).
- **Real-Time Transport:** Native browser `WebSocket` connected to `ws://<host>/ws/{session_id}` with automatic reconnect backoff.
- **QR Generator:** `QRCode.js` (`https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js`) to render dynamic 5-minute tokens on the projector screen.
- **Data Visualization:** `Chart.js` (via CDN) for real-time poll/quiz response bar charts.

---

## 2. Directory Structure (`/static`)
```text
static/
├── index.html          # Lecturer Dashboard (Desktop-first, tabbed layout)
├── student.html        # Student Mobile View (Mobile-first, accessed via QR)
├── forum.html          # Class Q&A / Blog Feed (Shared view)
└── js/
    ├── api.js          # Axios instance, interceptors, and API wrapper functions
    ├── ws.js           # WebSocket client manager & event dispatcher
    ├── lecturer.js     # Controller logic for index.html
    └── student.js      # Controller logic for student.html
```

---

## 3. Page Specifications & User Flows

### 3.1 `index.html` (Lecturer Control Center)
Single-page tabbed interface connected via WebSocket on page load:

1. **Tab 1: Live Quiz & Instant Polls**
   - **Excel Upload:** File input (`.xlsx`) sent via `axios.post('/api/quiz/upload-excel', formData)`. Displays loaded question list.
   - **5-Minute Timed Question:** Clicking "Launch Question" calls `POST /api/quiz/trigger`. Renders the returned URL (`http://<host>/s/{token}`) as a large QR code via `QRCode.js` alongside a live `05:00` countdown timer.
   - **KISS Poll:** Quick text input + "Broadcast Poll" button (`POST /api/poll/create`).
   - **Live Telemetry:** Listens to WebSocket `QUIZ_UPDATE` and `POLL_UPDATE` events to dynamically update `Chart.js` bars and submission counters without page refresh.

2. **Tab 2: Lecture Video Summarizer & HW Review**
   - **Upload Zone:** File selector for Zoom/Meet `.mp4`/`.m4a` recordings using `axios.post('/api/ai/summarize-lecture', formData, { onUploadProgress })` with a visual progress bar.
   - **Async Result:** Displays a loading spinner until WebSocket emits `SUMMARY_READY`, then renders formatted Markdown/HTML key takeaways.
   - **HW Comparison:** Input field for repository URLs -> `POST /api/ai/review-homework` -> displays comparative rubric table.

3. **Tab 3: Minimal Attendance Control**
   - Displays current active tracking status (`YOLOv8 + ByteTrack Active`).
   - **"End Session & Download CSV" Button:** Calls `POST /api/attendance/stop` or `GET /api/attendance/export` with `responseType: 'blob'` in Axios to trigger an immediate `.csv` / `.xlsx` file download.

### 3.2 `student.html` (Mobile-First QR Landing Page)
- **Entry Point:** Accessed directly via QR scan (`/s/{token}`). No login/password required.
- **UI Components:**
  - Clean mobile card (`max-w-md mx-auto`).
  - Input fields: `Full Name` & `Student ID`.
  - Question prompt + large touch-friendly radio buttons (`A / B / C / D` or `True / False`).
  - Submit button calling `axios.post('/api/quiz/submit', payload)`.
- **State Handling:**
  - On `200 OK`: Replaces form with green confirmation badge ("Response Recorded").
  - On `403 / 410 Gone` (Axios error interceptor): Displays clear warning ("The 5-minute submission window has closed").

### 3.3 `forum.html` (Course Forum: Threads & Replies)
- **Plain REST over Axios, no WebSockets** (KISS). The page does not refresh by itself; new content from others appears when the course is reopened or the page is reloaded.
- **Course tabs:** Lists only the courses the logged-in user teaches (lecturers, `lecturer_id` match) or is approved for (students, `enrollment_status === "approved"`). The last opened course is remembered in `localStorage` (`smartclass_forum_course`).
- **Thread list:** `GET /api/courses/{course_id}/posts?user_id=…` returns the course's threads (newest first), each with its nested replies (oldest first).
- **New thread:** Title + message form → `POST /api/courses/{course_id}/posts`.
- **Replies:** Inline "Add a reply..." input under every thread → `POST /api/posts/{post_id}/comments`.
- New threads and replies are inserted into the page from the API response straight away (no full re-render), followed by a toast.
- Empty state when a course has no threads: "No discussions in this course yet. Start the conversation!"
- Users who are not logged in are shown a link to `/login`.

---

## 4. WebSocket Event Contract (`ws://<host>/ws/{session_id}`)

| Event Type (`event`) | Direction | Payload (`data`) | Frontend Action |
| :--- | :--- | :--- | :--- |
| `QUIZ_UPDATE` | Server -> Client | `{ total_responses, option_counts }` | Update live response counter & chart |
| `POLL_UPDATE` | Server -> Client | `{ poll_id, results: { opt1, opt2 } }` | Re-render Chart.js dataset |
| `SUMMARY_READY` | Server -> Client | `{ session_id, markdown_summary }` | Hide spinner and display AI lecture summary |
| `ATTENDANCE_DONE` | Server -> Client | `{ download_url, total_present }` | Show toast notification with direct CSV link |
| `NEW_FORUM_POST` | Server -> Client | `{ id, author, content, timestamp }` | Legacy global feed only (AI summaries via `/api/forum/posts`). `forum.html` no longer listens to it. |