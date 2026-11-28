"""Tests for Phase 1 functional gaps: F1-F5 and student roster import."""

import io
import openpyxl

from app.services.ai_service import AIServiceAgent
from app.services.attendance_service import attendance_manager
from tests.conftest import (
    DEFAULT_LECTURER_ID,
    create_course,
    enroll,
    login_student,
    start_session,
)


def test_self_checkin_qr_flow_and_xlsx_export(client):
    session_id = start_session(client)
    trig = client.post(
        "/api/attendance/checkin/trigger",
        json={"session_id": session_id, "lecturer_id": DEFAULT_LECTURER_ID, "ttl_seconds": 300},
    )
    assert trig.status_code == 200
    token = trig.json()["token"]
    assert trig.json()["qr_path"] == f"/checkin/{token}"

    info = client.get(f"/api/attendance/checkin/{token}")
    assert info.status_code == 200
    assert info.json()["session_id"] == session_id

    sub = client.post(
        "/api/attendance/checkin/submit",
        json={"token": token, "student_id": "300000101", "full_name": "Self Checkin Sara"},
    )
    assert sub.status_code == 200
    assert sub.json()["status"] == "checked_in"

    status_res = client.get(f"/api/attendance/status/{session_id}").json()
    assert status_res["total_tracked"] == 1
    row = status_res["records"][0]
    assert row["source"] == "self_checkin"
    assert row["presence_status"] == "Present"

    xlsx_res = client.get("/api/attendance/export-xlsx", params={"session_id": session_id})
    assert xlsx_res.status_code == 200
    wb = openpyxl.load_workbook(io.BytesIO(xlsx_res.content))
    headers = [c.value for c in wb.active[1]]
    assert headers == [
        "student_id",
        "name",
        "checked_in_at",
        "camera_dwell_minutes",
        "presence_status",
        "source",
    ]


def test_count_photo_and_video_sampling_modes(client, monkeypatch):
    photo_res = client.post(
        "/api/attendance/count-photo",
        files={"file": ("class.jpg", b"fake-photo-bytes", "image/jpeg")},
    )
    assert photo_res.status_code == 200
    assert photo_res.json()["count"] >= 3
    assert len(photo_res.json()["boxes"]) == photo_res.json()["count"]

    session_id = start_session(client)
    monkeypatch.setattr(
        attendance_manager.tracker,
        "detect_video_tracks",
        lambda *_args, **_kwargs: {1: 3, 2: 2},
    )
    attendance_manager.tracker.mode = "yolo_video"
    vid_res = client.post(
        "/api/attendance/frame",
        data={"session_id": session_id, "interval_seconds": "5"},
        files={"file": ("lecture.mp4", b"fake-video", "video/mp4")},
    )
    assert vid_res.status_code == 200
    assert vid_res.json()["detector_mode"] == "yolo_video"
    assert vid_res.json()["detected_count"] == 2


def test_poll_close_blocks_further_votes_and_broadcasts(client):
    session_id = start_session(client)
    poll = client.post(
        "/api/poll/create",
        json={"session_id": session_id, "prompt": "Ready?", "option_1": "Yes", "option_2": "No"},
    ).json()

    with client.websocket_connect(f"/ws/{session_id}") as ws:
        closed = client.post(f"/api/poll/{poll['poll_id']}/close")
        assert closed.status_code == 200
        assert closed.json()["is_open"] is False
        msg = ws.receive_json()
        assert msg["event"] == "POLL_UPDATE"
        assert msg["data"]["is_open"] is False

    late_vote = client.post(
        "/api/poll/vote",
        json={"poll_id": poll["poll_id"], "selected_option": "Yes"},
    )
    assert late_vote.status_code == 403


def test_course_forum_broadcasts_and_private_message_read(client):
    course = create_course(client, "WS Course", DEFAULT_LECTURER_ID)
    login_student(client, "300000202", "Maya")
    enroll(client, "300000202", course["id"], approve=True)

    with client.websocket_connect(f"/ws/course:{course['id']}") as ws:
        post = client.post(
            f"/api/courses/{course['id']}/posts",
            json={"author_id": "300000202", "title": "Q1", "content": "Hello"},
        )
        assert post.status_code == 201
        ev1 = ws.receive_json()
        assert ev1["event"] == "FORUM_THREAD_NEW"
        assert ev1["data"]["title"] == "Q1"

        comment = client.post(
            f"/api/posts/{post.json()['id']}/comments",
            json={"author_id": DEFAULT_LECTURER_ID, "content": "Reply"},
        )
        assert comment.status_code == 201
        ev2 = ws.receive_json()
        assert ev2["event"] == "FORUM_COMMENT_NEW"
        assert ev2["data"]["comment"]["content"] == "Reply"

    # Private message live broadcast + mark as read
    with client.websocket_connect("/ws/global") as ws:
        pm = client.post(
            "/api/forum/posts",
            json={
                "author_id": "300000202",
                "author_name": "Maya",
                "author_role": "student",
                "post_type": "private_message",
                "content": "Can we review SOLID?",
            },
        )
        assert pm.status_code == 200
        assert pm.json()["is_read"] is False
        ev = ws.receive_json()
        assert ev["event"] == "STUDENT_MESSAGE_NEW"

    read_res = client.post(f"/api/forum/posts/{pm.json()['id']}/read")
    assert read_res.status_code == 200
    assert read_res.json()["is_read"] is True


def test_vtt_srt_parsing_and_unavailable_audio_and_course_publish(client):
    vtt = "WEBVTT\n\n00:00:01.000 --> 00:00:04.000\nWelcome to OOD\n"
    parsed = AIServiceAgent.parse_subtitle_transcript(vtt)
    assert "[00:00:01] Welcome to OOD" in parsed

    course = create_course(client, "Summary Course", DEFAULT_LECTURER_ID)
    res_vtt = client.post(
        "/api/ai/summarize-lecture",
        data={"course_id": course["id"], "course_name": course["name"]},
        files={"file": ("lec.vtt", vtt.encode("utf-8"), "text/vtt")},
    )
    assert res_vtt.status_code == 200
    assert res_vtt.json()["transcription_available"] is True
    assert res_vtt.json()["course_id"] == course["id"]
    assert "Key Definitions" in res_vtt.json()["markdown_summary"]

    # Audio upload without OPENAI_API_KEY or faster-whisper reports transcription_available=False
    res_mp4 = client.post(
        "/api/ai/summarize-lecture",
        data={"course_name": "Intro"},
        files={"file": ("clip.mp4", b"fake-mp4-bytes", "video/mp4")},
    )
    assert res_mp4.status_code == 200
    assert res_mp4.json()["transcription_available"] is False
    assert "Transcription Unavailable" in res_mp4.json()["markdown_summary"]


def test_homework_static_inspection_tfidf_similarity_and_student_filter(client, tmp_path):
    repo_dir = tmp_path / "sample_repo"
    repo_dir.mkdir()
    (repo_dir / "README.md").write_text("# Sample Project\nClean architecture.", encoding="utf-8")
    (repo_dir / "main.py").write_text("class Policy:\n    pass\n", encoding="utf-8")
    (repo_dir / "test_main.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")

    snap = AIServiceAgent._inspect_directory(repo_dir)
    assert snap["fetched"] is True
    assert snap["file_count"] == 3
    assert snap["test_file_count"] == 1

    sim = AIServiceAgent._compute_tfidf_similarity_matrix(
        ["class A:\n    def run(self): return 1", "class A:\n    def run(self): return 1"]
    )
    assert sim[0][1] >= 0.99

    res = client.post(
        "/api/ai/review-homework",
        json={
            "student_id": "300000777",
            "repo_urls": [
                "https://github.com/student1/repo-a",
                "https://github.com/student2/repo-b",
            ],
        },
    )
    assert res.status_code == 200
    assert res.json()["count"] == 2
    assert "rubric" in res.json()["reviews"][0]
    assert "similarity" in res.json()["reviews"][0]

    filtered = client.get("/api/ai/reviews", params={"student_id": "300000777"}).json()
    assert len(filtered) == 2


def test_import_course_students_names_only(client):
    course = create_course(client, "Roster Course", DEFAULT_LECTURER_ID)
    csv_bytes = b"name\nAlice Cohen\nBob Levi\n"
    res = client.post(
        f"/api/courses/{course['id']}/import-students",
        files={"file": ("roster.csv", csv_bytes, "text/csv")},
    )
    assert res.status_code == 200
    assert res.json()["imported_count"] == 2
    first_id = res.json()["students"][0]["student_id"]
    assert first_id.startswith("stu_")


def test_public_config_endpoint_exposes_public_base_url(client, monkeypatch):
    from app.config import settings

    monkeypatch.setattr(settings, "PUBLIC_BASE_URL", "http://192.168.1.42:8000")
    res = client.get("/api/config")
    assert res.status_code == 200
    assert res.json()["public_base_url"] == "http://192.168.1.42:8000"
