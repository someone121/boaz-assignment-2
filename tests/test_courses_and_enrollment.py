"""Course catalog, enrollment workflow, and lecturer reassignment."""

from tests.conftest import (
    DEFAULT_LECTURER_ID,
    create_course,
    enroll,
    login_lecturer,
    login_student,
)


def test_create_course_shows_lecturer_name(client):
    login_lecturer(client, "400000010", full_name="Dr. Cohen")
    course = create_course(client, "Compilers", "400000010")
    assert course["name"] == "Compilers"
    assert course["lecturer_name"] == "Dr. Cohen"


def test_course_without_lecturer_has_placeholder_name(client):
    course = create_course(client, "Orphan Course", None)
    assert course["lecturer_name"] == "Course Instructor"


def test_enrollment_pending_then_approved(client):
    login_student(client, "300000010")
    course = create_course(client, "Databases", DEFAULT_LECTURER_ID)

    pending = enroll(client, "300000010", course["id"], approve=False)
    assert pending["status"] == "pending"

    listed = client.get("/api/enroll/pending").json()
    assert [e["id"] for e in listed] == [pending["id"]]

    by_student = {c["id"]: c for c in client.get("/api/courses", params={"student_id": "300000010"}).json()}
    assert by_student[course["id"]]["enrollment_status"] == "pending"

    approved = client.post("/api/enroll/approve", json={"enrollment_id": pending["id"]}).json()
    assert approved["status"] == "approved"
    assert client.get("/api/enroll/pending").json() == []

    by_student = {c["id"]: c for c in client.get("/api/courses", params={"student_id": "300000010"}).json()}
    assert by_student[course["id"]]["enrollment_status"] == "approved"


def test_duplicate_enrollment_returns_existing(client):
    login_student(client, "300000011")
    course = create_course(client, "Networks", DEFAULT_LECTURER_ID)
    first = enroll(client, "300000011", course["id"], approve=False)
    second = enroll(client, "300000011", course["id"], approve=False)
    assert first["id"] == second["id"]


def test_approve_by_student_and_course(client):
    login_student(client, "300000012")
    course = create_course(client, "Graphics", DEFAULT_LECTURER_ID)
    enroll(client, "300000012", course["id"], approve=False)
    res = client.post(
        "/api/enroll/approve",
        json={"student_id": "300000012", "course_id": course["id"]},
    )
    assert res.status_code == 200
    assert res.json()["status"] == "approved"


def test_enrollment_errors(client):
    assert (
        client.post("/api/enroll", json={"student_id": "300000013", "course_id": "missing"}).status_code
        == 404
    )
    assert client.post("/api/enroll/approve", json={}).status_code == 400
    assert client.post("/api/enroll/approve", json={"enrollment_id": 9999}).status_code == 404


def test_reassign_course_lecturer(client):
    login_lecturer(client, "400000011", full_name="Dr. New")
    course = create_course(client, "Security", DEFAULT_LECTURER_ID)

    res = client.patch(
        f"/api/courses/{course['id']}/lecturer",
        json={"acting_lecturer_id": DEFAULT_LECTURER_ID, "lecturer_id": "400000011"},
    )
    assert res.status_code == 200
    assert res.json()["lecturer_id"] == "400000011"
    assert res.json()["lecturer_name"] == "Dr. New"


def test_reassign_requires_lecturer_actor(client):
    login_student(client, "300000014")
    course = create_course(client, "AI", DEFAULT_LECTURER_ID)
    res = client.patch(
        f"/api/courses/{course['id']}/lecturer",
        json={"acting_lecturer_id": "300000014", "lecturer_id": DEFAULT_LECTURER_ID},
    )
    assert res.status_code == 403


def test_reassign_target_must_be_existing_lecturer(client):
    login_student(client, "300000015")
    course = create_course(client, "ML", DEFAULT_LECTURER_ID)
    for target in ("300000015", "nobody"):
        res = client.patch(
            f"/api/courses/{course['id']}/lecturer",
            json={"acting_lecturer_id": DEFAULT_LECTURER_ID, "lecturer_id": target},
        )
        assert res.status_code == 400


def test_reassign_unknown_course(client):
    res = client.patch(
        "/api/courses/missing/lecturer",
        json={"acting_lecturer_id": DEFAULT_LECTURER_ID, "lecturer_id": DEFAULT_LECTURER_ID},
    )
    assert res.status_code == 404
