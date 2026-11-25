"""Login/registration rules and startup seeding (default courses + default lecturer)."""

import app.main as main
from app.main import DEFAULT_COURSE_NAMES, _seed_default_courses, _seed_default_lecturer
from app.models import Course, User
from tests.conftest import DEFAULT_LECTURER_ID, DEFAULT_LECTURER_PASSWORD, login_lecturer, login_student

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


def test_student_first_login_creates_profile(client, db):
    user = login_student(client, "300000001", "Dana Levi")
    assert user["role"] == "student"
    assert user["full_name"] == "Dana Levi"
    assert user["id_number"] == user["user_id"] == "300000001"

    # Second login without a name keeps the stored name.
    again = client.post("/api/auth/login", json={"id_number": "300000001", "role": "student"})
    assert again.status_code == 200
    assert again.json()["full_name"] == "Dana Levi"


def test_role_is_inferred_from_password(client):
    res = client.post("/api/auth/login", json={"id_number": "400000001", "password": "pw"})
    assert res.status_code == 200
    assert res.json()["role"] == "lecturer"


def test_lecturer_wrong_password_is_rejected(client):
    login_lecturer(client, "400000002", password="right")
    res = client.post(
        "/api/auth/login",
        json={"id_number": "400000002", "role": "lecturer", "password": "wrong"},
    )
    assert res.status_code == 401


def test_lecturer_without_password_is_rejected(client):
    res = client.post("/api/auth/login", json={"id_number": "400000003", "role": "lecturer"})
    assert res.status_code == 400


def test_missing_id_is_rejected(client):
    assert client.post("/api/auth/login", json={"role": "student"}).status_code == 400


def test_student_id_cannot_log_in_as_lecturer(client):
    login_student(client, "300000002")
    res = client.post(
        "/api/auth/login",
        json={"id_number": "300000002", "role": "lecturer", "password": "pw"},
    )
    assert res.status_code == 403


def test_lecturer_id_cannot_log_in_as_student(client):
    login_lecturer(client, "400000004")
    res = client.post("/api/auth/login", json={"id_number": "400000004", "role": "student"})
    assert res.status_code == 403


# ---------------------------------------------------------------------------
# Seeding
# ---------------------------------------------------------------------------


def test_startup_seeds_courses_and_default_lecturer(client, db):
    courses = db.query(Course).all()
    assert sorted(c.name for c in courses) == sorted(DEFAULT_COURSE_NAMES)
    assert all(c.lecturer_id == DEFAULT_LECTURER_ID for c in courses)

    lecturer = db.get(User, DEFAULT_LECTURER_ID)
    assert lecturer is not None
    assert lecturer.role == "lecturer"


def test_default_lecturer_can_log_in(client):
    res = client.post(
        "/api/auth/login",
        json={"id_number": DEFAULT_LECTURER_ID, "role": "lecturer", "password": DEFAULT_LECTURER_PASSWORD},
    )
    assert res.status_code == 200
    assert res.json()["role"] == "lecturer"


def test_seeding_is_idempotent(client, db):
    # Running the startup seed again (as on every restart) must not duplicate anything.
    _seed_default_courses()
    _seed_default_lecturer()
    assert db.query(Course).count() == len(DEFAULT_COURSE_NAMES)
    assert db.query(User).filter(User.role == "lecturer").count() == 1


def test_seeding_does_not_reset_existing_password(client, db, monkeypatch):
    monkeypatch.setattr(main.settings, "DEFAULT_LECTURER_PASSWORD", "a-new-password")
    _seed_default_lecturer()
    old = client.post(
        "/api/auth/login",
        json={"id_number": DEFAULT_LECTURER_ID, "role": "lecturer", "password": DEFAULT_LECTURER_PASSWORD},
    )
    assert old.status_code == 200


def test_seeding_never_promotes_a_student(client, db, monkeypatch):
    login_student(client, "300000099")
    db.query(Course).update({Course.lecturer_id: None})
    db.commit()

    monkeypatch.setattr(main.settings, "DEFAULT_LECTURER_ID", "300000099")
    _seed_default_lecturer()

    db.expire_all()
    assert db.get(User, "300000099").role == "student"
    assert all(c.lecturer_id is None for c in db.query(Course).all())


def test_new_default_lecturer_only_takes_unassigned_courses(client, db, monkeypatch):
    monkeypatch.setattr(main.settings, "DEFAULT_LECTURER_ID", "555555555")
    _seed_default_lecturer()

    db.expire_all()
    assert db.get(User, "555555555").role == "lecturer"
    # The sample courses already belong to the first default lecturer.
    assert all(c.lecturer_id == DEFAULT_LECTURER_ID for c in db.query(Course).all())


def test_empty_default_lecturer_id_skips_seeding(session_factory, monkeypatch):
    monkeypatch.setattr(main.settings, "DEFAULT_LECTURER_ID", "  ")
    from app.database import init_db

    init_db()
    _seed_default_courses()
    _seed_default_lecturer()

    with session_factory() as db:
        assert db.query(User).count() == 0
        assert all(c.lecturer_id is None for c in db.query(Course).all())
