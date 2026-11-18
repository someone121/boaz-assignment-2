"""FastAPI application entrypoint and core session/auth endpoints for SmartClass AI."""

from contextlib import asynccontextmanager
import hashlib
import uuid

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.config import STATIC_DIR, settings
from app.database import SessionLocal, get_db, init_db
from app.models import Course, LectureSession, Student, User, utcnow
from app.routers import ai, attendance, courses, forum, polls, quiz, ws
from app.schemas import (
    LoginRequest,
    SessionReportResponse,
    SessionResponse,
    SessionStartRequest,
    UserResponse,
)
from app.services.attendance_service import attendance_manager


def _seed_default_courses() -> None:
    """Populate sample academic courses on first run so students can request enrollment."""
    db = SessionLocal()
    try:
        if db.query(Course).count() == 0:
            for name in (
                "Introduction to Software Engineering (I2SE)",
                "Object-Oriented Programming (OOP)",
                "Algorithms & Data Structures",
            ):
                db.add(Course(id=str(uuid.uuid4()), name=name, created_at=utcnow()))
            db.commit()
    finally:
        db.close()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Initialize SQLite schema, seed sample courses, and ensure directories exist."""
    init_db()
    _seed_default_courses()
    yield


settings.ensure_directories()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "KISS-oriented Web-Based Teaching Tool with CV Attendance, "
        "5-Min QR Quizzes, Live Polls & AI Workflows."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

app.include_router(attendance.router)
app.include_router(courses.router)
app.include_router(quiz.router)
app.include_router(polls.router)
app.include_router(forum.router)
app.include_router(ai.router)
app.include_router(ws.router)


def _hash_password(password: str) -> str:
    """Create a deterministic salted SHA-256 digest for local demo lecturer auth."""
    return hashlib.sha256(f"{settings.SECRET_KEY}:{password}".encode("utf-8")).hexdigest()


def _serve_static_page(filename: str) -> FileResponse:
    """Serve an HTML page from /static or raise 404 if missing."""
    page_path = STATIC_DIR / filename
    if not page_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Frontend page '{filename}' not found.",
        )
    return FileResponse(str(page_path))


@app.get("/", include_in_schema=False)
@app.get("/login", include_in_schema=False)
def login_page() -> FileResponse:
    """Serve the unified Student / Lecturer login page."""
    return _serve_static_page("login.html")


@app.get("/lecturer_dashboard", include_in_schema=False)
@app.get("/dashboard", include_in_schema=False)
def lecturer_dashboard_page() -> FileResponse:
    """Serve the Lecturer Control Center."""
    return _serve_static_page("lecturer_dashboard.html")


@app.get("/student_dashboard", include_in_schema=False)
@app.get("/live", include_in_schema=False)
@app.get("/s/{token}", include_in_schema=False)
def student_dashboard_page(token: str | None = None) -> FileResponse:
    """Serve the Mobile-First Student Dashboard (direct or via QR /s/{token})."""
    return _serve_static_page("student_dashboard.html")


@app.get("/forum", include_in_schema=False)
def class_forum_page() -> FileResponse:
    """Serve the shared Class Q&A / Blog Feed."""
    return _serve_static_page("forum.html")


@app.get("/api/health", tags=["Core"])
def health_check(db: Session = Depends(get_db)) -> dict:
    """Verify FastAPI server and SQLite database connectivity."""
    db.execute(text("SELECT 1"))
    return {
        "status": "ok",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "database": "connected",
    }


@app.post("/api/auth/login", response_model=UserResponse, tags=["Auth"])
def login_or_register(payload: LoginRequest, db: Session = Depends(get_db)) -> User:
    """Log in or auto-create a local profile (ID for students, ID + password for lecturers)."""
    id_value = (payload.id_number or payload.user_id or "").strip()
    if len(id_value) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A valid ID number is required.",
        )

    role = payload.role or ("lecturer" if payload.password else "student")
    user = db.get(User, id_value)
    display_name = (payload.full_name or "").strip() or (
        user.full_name if user else f"{role.title()} {id_value}"
    )

    if role == "lecturer":
        if not payload.password:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Lecturers must provide a password.",
            )
        password_hash = _hash_password(payload.password)
        if user is not None:
            if user.role != "lecturer":
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="ID is already registered as a student.",
                )
            if user.password_hash != password_hash:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Invalid lecturer password.",
                )
            return user

        user = User(
            user_id=id_value,
            full_name=display_name,
            email=payload.email,
            role="lecturer",
            password_hash=password_hash,
            is_approved=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    if user is None:
        user = User(
            user_id=id_value,
            full_name=display_name,
            email=payload.email,
            role="student",
            password_hash=None,
            is_approved=True,
        )
        db.add(user)
    elif user.role != "student":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="ID is registered as a lecturer. Please enter your password.",
        )

    student = db.get(Student, id_value)
    if student is None:
        db.add(Student(student_id=id_value, full_name=display_name, email=payload.email))

    db.commit()
    db.refresh(user)
    return user


@app.post("/api/session/start", response_model=SessionResponse, tags=["Sessions"])
def start_session(payload: SessionStartRequest, db: Session = Depends(get_db)) -> LectureSession:
    """Create and activate a new classroom lecture session."""
    session = LectureSession(
        id=str(uuid.uuid4()),
        course_name=payload.course_name,
        course_id=payload.course_id,
        lecturer_id=payload.lecturer_id,
        start_time=utcnow(),
        is_active=True,
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


@app.get("/api/sessions", response_model=list[SessionResponse], tags=["Sessions"])
def list_sessions(db: Session = Depends(get_db)) -> list[LectureSession]:
    """List classroom lecture sessions ordered newest first."""
    return db.query(LectureSession).order_by(LectureSession.start_time.desc()).all()


@app.get(
    "/api/sessions/{session_id}/report",
    response_model=SessionReportResponse,
    tags=["Sessions"],
)
def get_session_report(session_id: str, db: Session = Depends(get_db)) -> SessionReportResponse:
    """Return post-recording attendance statistics for a lecture session."""
    lecture = db.get(LectureSession, session_id)
    if lecture is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")

    rows = attendance_manager.evaluate_attendance(db, session_id)
    is_mock = False

    if rows:
        total_detected = len(rows)
        total_present = sum(1 for row in rows if row["presence_status"] == "Present")
        students_left_early = max(0, total_detected - total_present)
        lecture.total_detected = total_detected
        lecture.students_left_early = students_left_early
        db.commit()
    elif lecture.total_detected > 0:
        total_detected = lecture.total_detected
        students_left_early = lecture.students_left_early
        total_present = max(0, total_detected - students_left_early)
    else:
        # Provide deterministic demo statistics when no CV frames have been uploaded yet.
        is_mock = True
        total_detected = 24
        students_left_early = 3
        total_present = 21

    duration_minutes = lecture.total_duration_minutes or max(
        1, int(((lecture.end_time or utcnow()) - lecture.start_time).total_seconds() // 60)
    )
    rate = round((total_present / total_detected) * 100, 1) if total_detected > 0 else 0.0

    return SessionReportResponse(
        session_id=lecture.id,
        course_name=lecture.course_name,
        is_active=lecture.is_active,
        total_duration_minutes=duration_minutes,
        total_detected=total_detected,
        students_left_early=students_left_early,
        total_present=total_present,
        attendance_rate_percent=rate,
        is_mock_data=is_mock,
    )
