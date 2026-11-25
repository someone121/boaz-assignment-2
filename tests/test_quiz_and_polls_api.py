"""HTTP-level behaviour of 5-minute QR quizzes and instant polls."""

from datetime import timedelta

import openpyxl
import pytest

from app.models import ActiveQuestionToken, Poll, utcnow
from tests.conftest import start_session

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


def _upload_bank(client, tmp_path, rows, session_id=None):
    path = tmp_path / "bank.xlsx"
    wb = openpyxl.Workbook()
    for row in rows:
        wb.active.append(row)
    wb.save(path)
    data = {"session_id": session_id} if session_id else {}
    with open(path, "rb") as f:
        return client.post("/api/quiz/upload-excel", data=data, files={"file": ("bank.xlsx", f, XLSX_MIME)})


@pytest.fixture()
def quiz(client, tmp_path):
    """A session with two uploaded questions (no header row) and the first one triggered."""
    session_id = start_session(client)
    res = _upload_bank(
        client,
        tmp_path,
        [
            ["2 + 2 = ?", "3", "4", "5", "6", "B"],
            ["Is SQLite serverless?", "True", "False", None, None, "A"],
        ],
        session_id,
    )
    assert res.json()["loaded_count"] == 2
    trig = client.post("/api/quiz/trigger", json={"session_id": session_id}).json()
    return {"session_id": session_id, **trig}


# ---------------------------------------------------------------------------
# Quiz
# ---------------------------------------------------------------------------


def test_trigger_returns_qr_path_and_bank_status(quiz):
    assert quiz["qr_path"] == f"/s/{quiz['token']}"
    assert quiz["ttl_seconds"] == 300
    assert quiz["remaining_questions"] == 1
    assert quiz["questions_exhausted"] is False


def test_token_lookup_hides_empty_options(client, quiz):
    res = client.get(f"/api/quiz/token/{quiz['token']}")
    assert res.status_code == 200
    body = res.json()
    assert body["options"] == {"A": "3", "B": "4", "C": "5", "D": "6"}
    assert 0 < body["seconds_remaining"] <= 300


def test_submit_marks_correctness_and_counts(client, quiz):
    def submit(sid, option):
        return client.post(
            "/api/quiz/submit",
            json={"token": quiz["token"], "student_id": sid, "full_name": "S", "selected_option": option},
        )

    right = submit("300000030", "b")  # lower-case is normalised
    wrong = submit("300000031", "A")
    assert right.json()["is_correct"] is True
    assert wrong.json()["is_correct"] is False
    assert wrong.json()["total_responses"] == 2
    assert wrong.json()["option_counts"] == {"A": 1, "B": 1, "C": 0, "D": 0}


def test_expired_token_is_rejected(client, quiz, db):
    row = db.get(ActiveQuestionToken, quiz["token"])
    row.expires_at = utcnow() - timedelta(seconds=1)
    db.commit()

    assert client.get(f"/api/quiz/token/{quiz['token']}").status_code == 410
    res = client.post(
        "/api/quiz/submit",
        json={"token": quiz["token"], "student_id": "300000032", "full_name": "Late", "selected_option": "A"},
    )
    assert res.status_code == 403


def test_unknown_token_is_404(client):
    assert client.get("/api/quiz/token/nope").status_code == 404
    res = client.post(
        "/api/quiz/submit",
        json={"token": "nope", "student_id": "300000033", "full_name": "X", "selected_option": "A"},
    )
    assert res.status_code == 404


def test_bank_exhaustion(client, quiz):
    session_id = quiz["session_id"]
    second = client.post("/api/quiz/trigger", json={"session_id": session_id}).json()
    assert second["questions_exhausted"] is True

    listing = client.get("/api/quiz/questions").json()
    assert listing["remaining"] == 0
    assert listing["questions_exhausted"] is True

    assert client.post("/api/quiz/trigger", json={"session_id": session_id}).status_code == 404


def test_trigger_with_empty_bank_is_404(client):
    session_id = start_session(client)
    assert client.post("/api/quiz/trigger", json={"session_id": session_id}).status_code == 404
    assert client.get("/api/quiz/questions").json()["questions_exhausted"] is False


def test_upload_with_only_header_is_400(client, tmp_path):
    res = _upload_bank(client, tmp_path, [["Question", "A", "B", "C", "D", "Correct"]])
    assert res.status_code == 400


def test_true_false_defaults_when_options_missing(client, tmp_path):
    res = _upload_bank(client, tmp_path, [["question", "a", "b"], ["The sky is blue"]])
    q = res.json()["questions"][0]
    assert (q["option_a"], q["option_b"], q["option_c"]) == ("True", "False", None)


# ---------------------------------------------------------------------------
# Polls
# ---------------------------------------------------------------------------


@pytest.fixture()
def poll(client):
    session_id = start_session(client)
    res = client.post(
        "/api/poll/create",
        json={
            "session_id": session_id,
            "prompt": "Pace?",
            "option_1": "Slow",
            "option_2": "OK",
            "option_3": "Fast",
        },
    )
    assert res.status_code == 200
    return res.json()


def test_poll_create_lists_only_given_options(poll):
    assert poll["options"] == ["Slow", "OK", "Fast"]
    assert poll["results"] == {"Slow": 0, "OK": 0, "Fast": 0}
    assert poll["is_open"] is True


def test_poll_votes_are_tallied_and_listed(client, poll):
    for option in ("OK", "OK", "Fast"):
        client.post("/api/poll/vote", json={"poll_id": poll["poll_id"], "selected_option": option})
    polls = client.get(f"/api/poll/{poll['session_id']}").json()
    assert polls[0]["results"] == {"Slow": 0, "OK": 2, "Fast": 1}
    assert polls[0]["total_votes"] == 3


def test_poll_vote_errors(client, poll, db):
    bad_option = client.post("/api/poll/vote", json={"poll_id": poll["poll_id"], "selected_option": "Maybe"})
    assert bad_option.status_code == 400

    missing = client.post("/api/poll/vote", json={"poll_id": "nope", "selected_option": "OK"})
    assert missing.status_code == 404

    db.get(Poll, poll["poll_id"]).is_open = False
    db.commit()
    closed = client.post("/api/poll/vote", json={"poll_id": poll["poll_id"], "selected_option": "OK"})
    assert closed.status_code == 403
