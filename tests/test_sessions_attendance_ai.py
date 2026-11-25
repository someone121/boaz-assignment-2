"""Lecture sessions, attendance reports, and AI endpoints."""

import csv
import io

from tests.conftest import start_session


def _send_frame(client, session_id, name="room.jpg", payload=b"fake-jpeg-bytes"):
    res = client.post(
        "/api/attendance/frame",
        data={"session_id": session_id, "interval_seconds": "5"},
        files={"file": (name, payload, "image/jpeg")},
    )
    assert res.status_code == 200, res.text
    return res.json()


def test_sessions_are_listed_newest_first(client):
    first = start_session(client, "First")
    second = start_session(client, "Second")
    ids = [s["id"] for s in client.get("/api/sessions").json()]
    assert ids.index(second) < ids.index(first)


def test_report_uses_demo_numbers_before_any_frame(client):
    session_id = start_session(client)
    report = client.get(f"/api/sessions/{session_id}/report").json()
    assert report["is_mock_data"] is True
    assert report["total_detected"] == 24
    assert report["is_active"] is True


def test_report_for_unknown_session_is_404(client):
    assert client.get("/api/sessions/missing/report").status_code == 404


def test_frame_uses_mock_tracker_and_accumulates(client):
    session_id = start_session(client)
    first = _send_frame(client, session_id)
    assert first["detector_mode"] == "mock_yolo_bytetrack"
    assert first["detected_count"] >= 3

    _send_frame(client, session_id)
    status = client.get(f"/api/attendance/status/{session_id}").json()
    assert status["total_tracked"] == first["total_tracked_unique"]
    assert all(r["dwell_seconds"] == 10 for r in status["records"])


def test_stop_closes_session_and_export_has_rows(client):
    session_id = start_session(client)
    detected = _send_frame(client, session_id)["detected_count"]

    stop = client.post("/api/attendance/stop", params={"session_id": session_id})
    assert stop.status_code == 200
    assert stop.json()["total_tracked"] == detected
    assert stop.json()["download_url"] == f"/api/attendance/export?session_id={session_id}"

    report = client.get(f"/api/sessions/{session_id}/report").json()
    assert report["is_active"] is False
    assert report["is_mock_data"] is False
    assert report["total_detected"] == detected

    export = client.get("/api/attendance/export", params={"session_id": session_id})
    assert export.status_code == 200
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert len(rows) == detected
    assert {"track_id", "student_id", "full_name", "presence_status"} <= set(rows[0])


def test_export_without_data_has_placeholder_row(client):
    session_id = start_session(client)
    export = client.get("/api/attendance/export", params={"session_id": session_id})
    rows = list(csv.DictReader(io.StringIO(export.text)))
    assert [r["full_name"] for r in rows] == ["No Attendance Data"]


def test_quiz_answer_links_student_to_a_track(client, tmp_path):
    import openpyxl

    session_id = start_session(client)
    _send_frame(client, session_id)

    path = tmp_path / "q.xlsx"
    wb = openpyxl.Workbook()
    wb.active.append(["Q?", "A", "B", None, None, "A"])
    wb.save(path)
    with open(path, "rb") as f:
        client.post("/api/quiz/upload-excel", files={"file": ("q.xlsx", f, "application/octet-stream")})
    token = client.post("/api/quiz/trigger", json={"session_id": session_id}).json()["token"]
    client.post(
        "/api/quiz/submit",
        json={"token": token, "student_id": "300000040", "full_name": "Linked Lior", "selected_option": "A"},
    )

    records = client.get(f"/api/attendance/status/{session_id}").json()["records"]
    assert any(r["student_id"] == "300000040" and r["full_name"] == "Linked Lior" for r in records)


def test_summary_is_stored_and_posted_to_legacy_feed(client):
    res = client.post(
        "/api/ai/summarize-lecture",
        data={"course_name": "Intro"},
        files={"file": ("talk.txt", b"We discussed SOLID.", "text/plain")},
    )
    assert res.status_code == 200
    assert "Main Concepts" in res.json()["markdown_summary"]

    summaries = client.get("/api/ai/summaries").json()
    assert summaries[0]["filename"] == "talk.txt"

    ai_posts = client.get("/api/forum/posts", params={"post_type": "ai_summary"}).json()
    assert ai_posts[0]["id"] == res.json()["forum_post_id"]
    assert ai_posts[0]["course_id"] is None  # not shown in the course forum


def test_homework_review_skips_blank_urls_and_is_listed(client):
    res = client.post(
        "/api/ai/review-homework",
        json={"repo_urls": ["https://github.com/a/ex2/", "   ", "https://github.com/b/hw"]},
    )
    assert res.status_code == 200
    labels = [r["submission_label"] for r in res.json()["reviews"]]
    assert labels == ["ex2", "hw"]
    assert len(client.get("/api/ai/reviews").json()) == 2


def test_homework_review_requires_urls(client):
    assert client.post("/api/ai/review-homework", json={"repo_urls": []}).status_code == 422
