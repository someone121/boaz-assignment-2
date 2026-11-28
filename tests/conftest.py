"""Shared pytest fixtures for SmartClass AI.

Every test that uses ``client`` gets:
* a fresh temporary SQLite database (same engine settings as production:
  WAL, foreign keys ON), used both by request handlers and by the startup
  seeding (default courses + default lecturer);
* temporary uploads/ and reports/ folders;
* the mock person tracker (no YOLO weights are loaded);
* no OpenAI key, so AI endpoints use the offline fallback.
"""

from fastapi.testclient import TestClient
import pytest
from sqlalchemy.orm import sessionmaker

import app.database as database
import app.main as main
import app.models  # noqa: F401  (registers all tables on Base.metadata)
from app.config import settings
from app.database import create_db_engine, get_db
from app.routers import ai as ai_router
from app.routers import quiz as quiz_router
from app.services import ai_service as ai_service_module
from app.services import attendance_service
from app.services.attendance_service import attendance_manager

DEFAULT_LECTURER_ID = settings.DEFAULT_LECTURER_ID
DEFAULT_LECTURER_PASSWORD = settings.DEFAULT_LECTURER_PASSWORD


@pytest.fixture()
def session_factory(tmp_path, monkeypatch):
    """Point the whole app (handlers + startup seeding) at a temporary database."""
    engine = create_db_engine(f"sqlite:///{(tmp_path / 'test_smartclass.db').as_posix()}")
    factory = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)

    # init_db() uses app.database.engine; the seed helpers use app.main.SessionLocal.
    monkeypatch.setattr(database, "engine", engine)
    monkeypatch.setattr(main, "SessionLocal", factory)

    # Keep uploaded files and CSV reports out of the real project folders.
    uploads = tmp_path / "uploads"
    reports = tmp_path / "reports"
    uploads.mkdir()
    reports.mkdir()
    monkeypatch.setattr(ai_router, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(quiz_router, "UPLOADS_DIR", uploads)
    monkeypatch.setattr(attendance_service, "REPORTS_DIR", reports)

    # Deterministic, offline behaviour.
    monkeypatch.setattr(settings, "OPENAI_API_KEY", "")
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    monkeypatch.setattr(attendance_manager.tracker, "_initialized", True)
    monkeypatch.setattr(attendance_manager.tracker, "_model", None)
    monkeypatch.setattr(
        ai_service_module.ai_service,
        "_fetch_repository_snapshot",
        lambda url: {
            "fetched": True,
            "error": None,
            "file_count": 4,
            "test_file_count": 1,
            "readme_length": 250,
            "loc": 120,
            "language_mix": {".py": 4},
            "code_corpus": f"class RepoSample:\n    def run(self):\n        return '{url}'\n",
            "prompt_context": f"Sample repo {url}",
        },
    )

    yield factory
    engine.dispose()


@pytest.fixture()
def db(session_factory):
    """A database session for arranging or inspecting state directly."""
    session = session_factory()
    try:
        yield session
    finally:
        session.close()


@pytest.fixture()
def client(session_factory):
    """FastAPI TestClient running the real startup (schema + seeding) on the temp database."""

    def override_get_db():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    main.app.dependency_overrides[get_db] = override_get_db
    with TestClient(main.app) as test_client:
        yield test_client
    main.app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Small helpers shared by test modules
# ---------------------------------------------------------------------------


def login_student(client, user_id: str, full_name: str = "Test Student") -> dict:
    res = client.post(
        "/api/auth/login",
        json={"id_number": user_id, "full_name": full_name, "role": "student"},
    )
    assert res.status_code == 200, res.text
    return res.json()


def login_lecturer(client, user_id: str, password: str = "pw123", full_name: str = "Dr. Test") -> dict:
    res = client.post(
        "/api/auth/login",
        json={"id_number": user_id, "full_name": full_name, "role": "lecturer", "password": password},
    )
    assert res.status_code == 200, res.text
    return res.json()


def create_course(client, name: str, lecturer_id: str | None) -> dict:
    res = client.post("/api/courses", json={"name": name, "lecturer_id": lecturer_id})
    assert res.status_code == 200, res.text
    return res.json()


def enroll(client, student_id: str, course_id: str, approve: bool = True) -> dict:
    res = client.post("/api/enroll", json={"student_id": student_id, "course_id": course_id})
    assert res.status_code == 200, res.text
    enrollment = res.json()
    if approve:
        res = client.post("/api/enroll/approve", json={"enrollment_id": enrollment["id"]})
        assert res.status_code == 200, res.text
        enrollment = res.json()
    return enrollment


def start_session(client, course_name: str = "Intro to SE", lecturer_id: str | None = None) -> str:
    res = client.post("/api/session/start", json={"course_name": course_name, "lecturer_id": lecturer_id})
    assert res.status_code == 200, res.text
    return res.json()["id"]
