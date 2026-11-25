"""Course forum: threads, replies, ordering, and server-side access control."""

import pytest

from app.models import ForumPost
from tests.conftest import (
    DEFAULT_LECTURER_ID,
    create_course,
    enroll,
    login_lecturer,
    login_student,
)


@pytest.fixture()
def course(client):
    """A course taught by the default lecturer with one approved and one pending student."""
    c = create_course(client, "Forum Course", DEFAULT_LECTURER_ID)
    login_student(client, "300000020", "Approved Amy")
    login_student(client, "300000021", "Pending Pete")
    enroll(client, "300000020", c["id"], approve=True)
    enroll(client, "300000021", c["id"], approve=False)
    return c


def _post(client, course_id, author_id, title="Hello", content="First message"):
    return client.post(
        f"/api/courses/{course_id}/posts",
        json={"author_id": author_id, "title": title, "content": content},
    )


def test_lecturer_and_approved_student_can_post_and_read(client, course):
    lect = _post(client, course["id"], DEFAULT_LECTURER_ID, "Welcome", "Course starts Sunday")
    assert lect.status_code == 201
    assert lect.json()["author_role"] == "lecturer"
    assert lect.json()["comments"] == []

    stud = _post(client, course["id"], "300000020", "Question", "Is attendance required?")
    assert stud.status_code == 201
    assert stud.json()["author_name"] == "Approved Amy"
    assert stud.json()["author_role"] == "student"

    for reader in (DEFAULT_LECTURER_ID, "300000020"):
        res = client.get(f"/api/courses/{course['id']}/posts", params={"user_id": reader})
        assert res.status_code == 200
        assert [p["title"] for p in res.json()] == ["Question", "Welcome"]  # newest first


def test_replies_are_nested_oldest_first(client, course):
    post_id = _post(client, course["id"], "300000020").json()["id"]

    r1 = client.post(f"/api/posts/{post_id}/comments", json={"author_id": DEFAULT_LECTURER_ID, "content": "first"})
    r2 = client.post(f"/api/posts/{post_id}/comments", json={"author_id": "300000020", "content": "second"})
    assert r1.status_code == r2.status_code == 201
    assert r1.json()["post_id"] == post_id

    posts = client.get(f"/api/courses/{course['id']}/posts", params={"user_id": "300000020"}).json()
    assert [c["content"] for c in posts[0]["comments"]] == ["first", "second"]


def test_pending_student_is_forbidden(client, course):
    assert client.get(f"/api/courses/{course['id']}/posts", params={"user_id": "300000021"}).status_code == 403
    assert _post(client, course["id"], "300000021").status_code == 403


def test_other_lecturer_is_forbidden(client, course):
    login_lecturer(client, "400000020")
    assert client.get(f"/api/courses/{course['id']}/posts", params={"user_id": "400000020"}).status_code == 403


def test_unenrolled_student_cannot_reply(client, course):
    post_id = _post(client, course["id"], DEFAULT_LECTURER_ID).json()["id"]
    login_student(client, "300000022")
    res = client.post(f"/api/posts/{post_id}/comments", json={"author_id": "300000022", "content": "hi"})
    assert res.status_code == 403


def test_unknown_user_gets_401(client, course):
    assert client.get(f"/api/courses/{course['id']}/posts", params={"user_id": "ghost"}).status_code == 401


def test_unknown_course_gets_404(client):
    assert client.get("/api/courses/nope/posts", params={"user_id": DEFAULT_LECTURER_ID}).status_code == 404


def test_user_id_query_param_is_required(client, course):
    assert client.get(f"/api/courses/{course['id']}/posts").status_code == 422


def test_reply_to_unknown_or_legacy_post_gets_404(client, course, db):
    res = client.post("/api/posts/9999/comments", json={"author_id": DEFAULT_LECTURER_ID, "content": "x"})
    assert res.status_code == 404

    legacy = ForumPost(course_name="General", author_name="AI", author_role="ai", post_type="ai_summary", content="s")
    db.add(legacy)
    db.commit()
    res = client.post(f"/api/posts/{legacy.id}/comments", json={"author_id": DEFAULT_LECTURER_ID, "content": "x"})
    assert res.status_code == 404


def test_blank_title_or_reply_is_rejected(client, course):
    assert _post(client, course["id"], DEFAULT_LECTURER_ID, title="   ").status_code == 400
    assert _post(client, course["id"], DEFAULT_LECTURER_ID, content="   ").status_code == 400

    post_id = _post(client, course["id"], DEFAULT_LECTURER_ID).json()["id"]
    res = client.post(f"/api/posts/{post_id}/comments", json={"author_id": DEFAULT_LECTURER_ID, "content": "  "})
    assert res.status_code == 400


def test_threads_are_scoped_to_their_course(client, course):
    other = create_course(client, "Other Course", DEFAULT_LECTURER_ID)
    _post(client, course["id"], DEFAULT_LECTURER_ID, title="In first")
    _post(client, other["id"], DEFAULT_LECTURER_ID, title="In second")

    titles = [
        p["title"]
        for p in client.get(f"/api/courses/{other['id']}/posts", params={"user_id": DEFAULT_LECTURER_ID}).json()
    ]
    assert titles == ["In second"]


def test_legacy_feed_filters_by_post_type(client, course):
    _post(client, course["id"], DEFAULT_LECTURER_ID)
    res = client.post(
        "/api/forum/posts",
        json={"author_name": "Stu", "post_type": "private_message", "content": "private"},
    )
    assert res.status_code == 200
    only_private = client.get("/api/forum/posts", params={"post_type": "private_message"}).json()
    assert [p["content"] for p in only_private] == ["private"]
