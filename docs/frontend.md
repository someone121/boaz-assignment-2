# Frontend

The frontend is plain HTML + vanilla ES6 modules in `static/`. FastAPI serves it directly. There is **no build step, no npm, and no framework**: edit a file and reload the browser.

See also: [backend.md](backend.md) · [docker.md](docker.md) · [../README.md](../README.md)

---

## 1. Stack

Everything is loaded from CDNs, so the browser needs internet access.

| What | Library | Used on |
| :--- | :--- | :--- |
| Styling | Tailwind CSS Play CDN (`cdn.tailwindcss.com`), configured inline per page | all pages |
| HTTP | Axios | all pages |
| QR codes | QRCode.js 1.0.0 | lecturer dashboard |
| Charts | Chart.js | lecturer dashboard |
| Fonts | Google Fonts: Inter, JetBrains Mono | all pages |
| Real-time | Native `WebSocket` | lecturer + student dashboards |

Theme colors (warm "coffee" palette) are set in each page's `tailwind.config`: `cream #fff8f0`, `caramel #c08552`, `mocha #8c5a3c`, `coffee #4b2e2b`.

---

## 2. Files

```text
static/
├── login.html               Login for students and lecturers
├── lecturer_dashboard.html  Lecturer control center (desktop-first, 4 tabs)
├── student_dashboard.html   Student view (mobile-first; also the QR landing page)
├── forum.html               Course forum (threads + replies)
└── js/
    ├── api.js        Axios instance + one wrapper function per backend endpoint
    ├── ws.js         SmartClassSocket: WebSocket client with auto-reconnect
    ├── ui.js         escapeHtml, showToast, renderEmptyState, validateUploadFile, renderSafeMarkdown
    ├── login.js      Controller for login.html
    ├── lecturer.js   Controller for lecturer_dashboard.html
    ├── student.js    Controller for student_dashboard.html
    └── forum.js      Controller for forum.html
```

Each page loads exactly one controller with `<script type="module" src="/static/js/<page>.js">`. Controllers import the shared modules with relative paths (`./api.js`).

---

## 3. URLs

| URL | Page |
| :--- | :--- |
| `/` or `/login` | `login.html` |
| `/lecturer_dashboard` (alias `/dashboard`) | `lecturer_dashboard.html` |
| `/student_dashboard` (alias `/live`) | `student_dashboard.html` |
| `/s/{token}` | `student_dashboard.html`, with the quiz for that QR token opened |
| `/checkin/{token}` | `student_dashboard.html`, with the self check-in card opened |
| `/forum` | `forum.html` |

---

## 4. Login state (`localStorage`)

There are no cookies or auth tokens. After login the profile returned by `POST /api/auth/login` is stored in the browser:

| Key | Content |
| :--- | :--- |
| `smartclass_user` | `{id_number, user_id, full_name, role}`: the source of truth every page reads |
| `smartclass_lecturer` / `smartclass_student` | Copy of the same profile for the matching role |
| `smartclass_forum_course` | Last course opened in the forum |

**Page guards:**

- Each dashboard has a small inline script in `<head>` that redirects before the page renders. The controller repeats the check.
  - Lecturer dashboard: no lecturer stored → `/`.
  - Student dashboard: no student stored → `/?redirect=<current path>`. After login, `login.js` sends students back there, so scanning a QR code while signed out still opens the quiz.
- The forum doesn't redirect; it shows a "please log in" message instead.
- **Sign out** removes the keys above and goes to `/`.

These guards are for convenience only. Real access checks happen on the server, and only for the course forum and course reassignment (see [backend.md §5](backend.md#5-authentication-and-access-control)).

---

## 5. Shared modules

### `api.js`

- `apiClient` is an Axios instance with the same-origin base URL and a 60 s timeout.
- A response interceptor adds to every error:
  - `error.friendlyMessage`: the server's `detail` text, or the Axios message;
  - `error.isWindowExpired = true` for `403` / `410`, used by the quiz screen.
- `export const api = {...}` has one method per endpoint, grouped as auth/sessions, courses/enrollment, attendance, quiz, polls, legacy forum, course forum and AI.
- Uploads use `FormData`.
- `downloadAttendanceCsv()` fetches a blob and clicks a temporary link to save it.

Controllers never call Axios directly. **Add new endpoints here.** `tests/test_frontend_contract.py` fails if a URL in this file has no backend route.

### `ws.js`

```js
const socket = new SmartClassSocket("global");
socket.onStatusChange = (s) => {/* "connected" | "reconnecting" */};
socket.on("POLL_UPDATE", (data) => {/* ... */});
socket.connect(sessionId);   // calling again switches channel
```

- Uses `wss:` automatically when the page is served over HTTPS.
- Reconnects with backoff: 1 s growing ×1.5 up to 15 s.
- Event names and payloads are listed in [backend.md §7](backend.md#7-websocket).

### `ui.js`

| Function | Use |
| :--- | :--- |
| `escapeHtml(text)` | **Always** escape user or server text before putting it in `innerHTML` |
| `showToast(msg, tone, linkHref?, linkLabel?)` | Bottom-right toast. Tones: `success`, `warning`, `error`, `info` |
| `renderEmptyState({title, subtitle})` | Dashed "nothing here yet" box |
| `validateUploadFile(file, exts, label)` | Rejects missing, empty, or wrong-extension files with a toast |
| `renderSafeMarkdown(md)` | Escapes first, then renders a small subset: `### `, `- `, `**bold**`, `` `code` `` |

---

## 6. Pages

### Login (`login.js`)

- Student / Lecturer toggle. The password field only appears for lecturers.
- The name field is optional and only used for a new profile.
- Unknown IDs create a new account (see the README for the default lecturer).
- If someone is already signed in: **Continue** goes to their dashboard, **Switch account** clears the stored profile.

### Lecturer dashboard (`lecturer.js`)

**Header**
- **Session picker.** Loads `/api/sessions` and selects the newest one. If there are none, it creates one called "Intro to Software Engineering".
- **New session.** Name field + **Start**.
- **View report** opens the session report modal.
- **Forum** link (new tab), and a **Live / Reconnecting** badge for the WebSocket.

Changing the session reconnects the WebSocket to that session's channel.

**Tab 1: Live Quiz & Instant Polls**
- **Question bank.** Upload a `.xlsx` file and see the list with a "remaining / total" badge. A warning shows when every question has been used.
- **5-minute QR challenge.**
  - Launches the next question, or a chosen one.
  - Draws a QR code for `<origin>/s/{token}` with a 05:00 countdown.
  - The answer chart updates live from `QUIZ_UPDATE`.
- **Instant poll.** Prompt + 2–4 options + **Close Poll** button. The bar chart updates live from `POLL_UPDATE`.

**Tab 2: AI Video Summary & HW Review**
- **Lecture summary.**
  - Upload `.mp4 .m4a .mp3 .wav .vtt .srt .txt .md`, with a progress bar.
  - The rendered summary appears when the request returns or when `SUMMARY_READY` arrives (or warns if transcription is unavailable).
  - A toast links to the forum.
- **Homework review.** One repository URL per line → cohort table with rubric scores, percentiles, and TF-IDF similarity flags.

**Tab 3: Attendance Control**
- **Start Webcam Stream.**
  - Uses `getUserMedia`, draws a frame to a `<canvas>` every 5 s and uploads it as JPEG.
- **Student Self Check-In QR.** Generates a 5-minute `/checkin/{token}` QR code; updates live on `ATTENDANCE_UPDATE`.
- **Count People in Class Photo.** Single photo upload returning person count and bounding-box annotated image.
- **File upload.** Image or video (`.jpg .jpeg .png .webp .mp4 .mov .avi`).
- **Live table** of sources (`camera`, `self_checkin`, `both`), minutes, and status.
- **End Session & Download CSV** + **Download .xlsx**.
- A list of past sessions, each with a **View Report** button.

**Tab 4: Pending Enrollments**
- Approve buttons for pending requests. The badge on the tab shows the count.
- **Manage Courses** creates a course and **Import Student Roster** imports a names-only `.csv`/`.xlsx`.
- **Student Messages / Suggestions** lists `private_message` posts live via `STUDENT_MESSAGE_NEW` with **Mark as Read**.

### Student dashboard (`student.js`)

- **Header:** name, ID, connection status, Forum link, sign out.
- **Quiz card.** Only shown on `/s/{token}`.
  - Loads the question, shows big radio buttons and a countdown.
  - Then shows a green "recorded" or a red "window closed" banner (`410` on load, `403` on submit).
- **Available courses.** Request to join a course; the status badge shows `pending` or `approved`.
- **Self check-in card.** Shown on `/checkin/{token}`; one tap on **"I'm Here"** marks attendance.
- **Live class poll.**
  - Shows the latest poll of the current session; displays `"Poll Closed"` and disables buttons when `is_open === false`.
- **Homework AI Review.** Submit a GitHub repo URL and view your personal rubric score and cohort comparison.
- **Private message to lecturer.** Sends a `private_message` to `/api/forum/posts`; queues in `localStorage` (`smartclass_offline_queue`) when offline and flushes on reconnect.

### Forum (`forum.js`)

- **Course tabs:** lecturers see their courses; students see courses with `approved` enrollment.
- **Real-time & offline:** Connects `SmartClassSocket` to `course:{courseId}` for live `FORUM_THREAD_NEW` and `FORUM_COMMENT_NEW` updates; queues posts/replies in `localStorage` when offline with a `Queued (offline)` badge and flushes on reconnect.
- "Back to Dashboard" links to the dashboard for your role.

---

## 7. Conventions

- **Escape everything** you put into `innerHTML` with `escapeHtml` (or `renderSafeMarkdown` for summaries).
- Show errors with `showToast(err.friendlyMessage || "...", "error")`.
- Use `renderEmptyState` for empty lists.
- Element IDs are kebab-case and controllers look them up by ID. **If you rename an ID in HTML, update the controller too.**
- Mobile-first for anything a student sees. Lecturer screens are desktop-first and use `lg:` breakpoints.

---

## 8. Adding a page

1. Create `static/<page>.html`. Copy the `<head>` of an existing page (Tailwind config, Axios, fonts, and the role guard if needed). End the body with `<script type="module" src="/static/js/<page>.js"></script>`.
2. Create `static/js/<page>.js` and import from `./api.js`, `./ui.js` and `./ws.js` as needed.
3. Add a route in `app/main.py` that returns `_serve_static_page("<page>.html")`.
4. Add the route to `PAGES` in `tests/test_frontend_contract.py`.

## 9. Testing

There is no JavaScript test runner. `tests/test_frontend_contract.py` (run with `python -m pytest`) checks that:

- every page route serves the right HTML file;
- every `/static/...` script tag and every `./module.js` import points at an existing file;
- every URL in `api.js` matches a real backend route;
- the dashboard role guards are present.

Check UI behaviour by hand in the browser. Open DevTools → Network/WS to watch API calls and WebSocket events.
