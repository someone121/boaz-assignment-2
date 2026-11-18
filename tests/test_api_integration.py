"""End-to-end integration tests for SmartClass AI REST APIs."""

from concurrent.futures import ThreadPoolExecutor

from fastapi.testclient import TestClient
import openpyxl
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

import app.models  # noqa: F401
from app.database import Base, get_db
from app.main import app as fastapi_app


@pytest.fixture()
def client(tmp_path):
    """Provide a FastAPI TestClient backed by an isolated temporary SQLite database."""
    db_file = tmp_path / "test_smartclass.db"
    engine = create_engine(
        f"sqlite:///{db_file.as_posix()}",
        connect_args={"check_same_thread": False},
    )

    Base.metadata.create_all(bind=engine)
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as test_client:
        yield test_client
    fastapi_app.dependency_overrides.clear()
    engine.dispose()


def test_full_classroom_workflow(client, tmp_path):
    """Verify health, auth, session, attendance CSV, quiz, poll, forum, and AI endpoints."""
    # 1. Health & Auth
    assert client.get("/api/health").status_code == 200
    assert (
        client.post(
            "/api/auth/login",
            json={"user_id": "999000111", "full_name": "Dr. Boaz", "role": "lecturer", "password": "secret"},
        ).status_code
        == 200
    )

    # 2. Start Session & Attendance Frame + Export
    sess_res = client.post(
        "/api/session/start",
        json={"course_name": "Intro to SE", "lecturer_id": "999000111"},
    )
    assert sess_res.status_code == 200
    session_id = sess_res.json()["id"]

    frame_res = client.post(
        "/api/attendance/frame",
        data={"session_id": session_id, "interval_seconds": "5"},
        files={"file": ("room.jpg", b"fake-jpeg-bytes", "image/jpeg")},
    )
    assert frame_res.status_code == 200
    assert frame_res.json()["detected_count"] >= 3

    export_res = client.get(f"/api/attendance/export?session_id={session_id}")
    assert export_res.status_code == 200
    assert "presence_status" in export_res.text

    # 3. Upload Excel, Trigger 5-Min QR, Concurrent Student Submissions
    xlsx_path = tmp_path / "quiz.xlsx"
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["Question", "Option A", "Option B", "Option C", "Option D", "Correct"])
    ws.append(["Which pattern decouples attendance policies?", "Strategy", "Singleton", "Factory", "Proxy", "A"])
    wb.save(xlsx_path)

    with open(xlsx_path, "rb") as f:
        upload_res = client.post(
            "/api/quiz/upload-excel",
            data={"session_id": session_id},
            files={"file": ("quiz.xlsx", f, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")},
        )
    assert upload_res.status_code == 200
    assert upload_res.json()["loaded_count"] == 1

    trig_res = client.post("/api/quiz/trigger", json={"session_id": session_id})
    assert trig_res.status_code == 200
    token = trig_res.json()["token"]
    assert trig_res.json()["questions_exhausted"] is True

    def submit_student(idx: int):
        return client.post(
            "/api/quiz/submit",
            json={
                "token": token,
                "student_id": f"2000000{idx:02d}",
                "full_name": f"Student {idx}",
                "selected_option": "A" if idx % 2 == 0 else "B",
            },
        )

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(submit_student, range(20)))
    assert all(r.status_code == 200 for r in results)

    # 4. Instant Poll
    poll_res = client.post(
        "/api/poll/create",
        json={"session_id": session_id, "prompt": "Clear so far?", "option_1": "Yes", "option_2": "No"},
    )
    assert poll_res.status_code == 200
    poll_id = poll_res.json()["poll_id"]
    vote_res = client.post(
        "/api/poll/vote",
        json={"poll_id": poll_id, "selected_option": "Yes", "student_id": "200000000"},
    )
    assert vote_res.status_code == 200
    assert vote_res.json()["results"]["Yes"] == 1

    # 5. AI Summary (auto-posts to forum) & Homework Review
    sum_res = client.post(
        "/api/ai/summarize-lecture",
        data={"session_id": session_id, "course_name": "Intro to SE"},
        files={"file": ("lecture.txt", b"Today we covered Strategy Pattern and FastAPI.", "text/plain")},
    )
    assert sum_res.status_code == 200
    assert "Main Concepts" in sum_res.json()["markdown_summary"]

    forum_res = client.get("/api/forum/posts")
    assert forum_res.status_code == 200
    assert any(p["post_type"] == "ai_summary" for p in forum_res.json())

    hw_res = client.post(
        "/api/ai/review-homework",
        json={
            "session_id": session_id,
            "repo_urls": ["https://github.com/student1/ex2", "https://github.com/student2/ex2"],
        },
    )
    assert hw_res.status_code == 200
    assert hw_res.json()["count"] == 2
