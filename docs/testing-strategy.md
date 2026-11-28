# Testing Strategy & Quality Assurance

## 1. Test Levels

1. **Unit Tests:** Pure domain logic (`PresencePolicy`, `TimedTokenManager`, `.xlsx` parser, `.vtt`/`.srt` parser, `_inspect_directory`, TF-IDF similarity).
2. **API & Integration Tests:** FastAPI `TestClient` against an isolated temporary SQLite database per test (`tests/conftest.py`), verifying status codes, DB state, and CSV/XLSX exports.
3. **WebSocket Tests:** `ConnectionManager` unit fan-out/dead-socket pruning + live `TestClient.websocket_connect` event delivery (`POLL_UPDATE`, `ATTENDANCE_DONE`, `FORUM_THREAD_NEW`, `FORUM_COMMENT_NEW`, `STUDENT_MESSAGE_NEW`).
4. **Frontend Contract Tests:** `tests/test_frontend_contract.py` verifies every HTML route, `<script>` tag, ES6 `./` import, role guard, and every URL in `static/js/api.js` against FastAPI's OpenAPI schema.
5. **Concurrency Test:** `ThreadPoolExecutor(max_workers=8)` firing 20 simultaneous `/api/quiz/submit` requests against SQLite WAL (`tests/test_api_integration.py`).
6. **Manual Mobile & E2E Demo Checklist:** Conducted on LAN IP prior to class using [DEMO.md](../DEMO.md).

---

## 2. Component-to-Test Mapping

| Component / Class | Test File(s) |
| :--- | :--- |
| `PresencePolicy` (`PercentagePresencePolicy`, `FixedTimePresencePolicy`) | `tests/test_presence_policy.py` |
| `VisionTracker` & `AttendanceManager` | `tests/test_sessions_attendance_ai.py`, `tests/test_phase1_features.py` |
| `TimedTokenManager` & `QuizSessionManager` | `tests/test_quiz_tokens.py`, `tests/test_excel_parser.py`, `tests/test_quiz_and_polls_api.py` |
| `poll_service` & `routers/polls.py` | `tests/test_quiz_and_polls_api.py`, `tests/test_phase1_features.py`, `tests/test_websocket.py` |
| `AIServiceAgent` & `routers/ai.py` | `tests/test_sessions_attendance_ai.py`, `tests/test_phase1_features.py` |
| `ConnectionManager` & `routers/ws.py` | `tests/test_websocket.py`, `tests/test_phase1_features.py` |
| `routers/courses.py` (`Course`, `Enrollment`, roster import) | `tests/test_courses_and_enrollment.py`, `tests/test_phase1_features.py` |
| `routers/forum.py` (`ForumPost`, `ForumComment`) | `tests/test_course_forum.py`, `tests/test_phase1_features.py` |
| `app/main.py` (Auth, seeding, session reports) | `tests/test_auth_and_seeding.py`, `tests/test_sessions_attendance_ai.py` |
| `static/*.html` & `static/js/api.js` | `tests/test_frontend_contract.py` |

---

## 3. Mocking Strategy (`tests/conftest.py`)

- **SQLite Isolation:** Each test receives a fresh temporary `test_smartclass.db` in `tmp_path` via `monkeypatch` on `database.engine` and `main.SessionLocal`.
- **YOLO / OpenCV:** `attendance_manager.tracker._initialized = True` and `_model = None` so tests run in deterministic `mock_yolo_bytetrack` mode without downloading weights (individual video-sampling tests monkeypatch `detect_video_tracks`).
- **OpenAI:** `settings.OPENAI_API_KEY = ""` forces deterministic offline fallback paths.
- **GitHub Cloning:** `ai_service._fetch_repository_snapshot` is monkeypatched in `conftest.py` so tests never make network calls; `_inspect_directory` and `_compute_tfidf_similarity_matrix` are tested directly against `tmp_path` repositories.

---

## 4. Running Tests & Measuring Coverage

```bash
# Run full suite (92 tests)
python -m pytest -q

# Measure coverage (target >= 80% on app/)
pip install pytest-cov
python -m pytest --cov=app --cov-report=term-missing
```

---

## 5. Manual Mobile & Demo Checklist

- [ ] Open Lecturer Dashboard via LAN IP (`http://<LAN_IP>:8000/`), not `localhost`.
- [ ] Log in as Lecturer (`111111111` / `admin123`) and verify redirect guard blocks unauthenticated access.
- [ ] Scan Check-In QR (`/checkin/{token}`) on a smartphone and tap **"I'm Here"**.
- [ ] Upload a class photo in **Count People in Class Photo** and verify bounding boxes appear.
- [ ] Launch a 5-minute Quiz QR (`/s/{token}`), submit from phone, and verify live Chart.js update.
- [ ] Broadcast a KISS Poll, vote on phone, click **Close Poll**, and verify `"Poll Closed"` appears on phone.
- [ ] Toggle Airplane Mode on phone, post in `/forum`, verify `Queued (offline)` badge, reconnect, and verify auto-flush.
