"""SQLAlchemy ORM models defining the SmartClass AI SQLite schema."""

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


def utcnow() -> datetime:
    """Return naive UTC timestamp for consistent SQLite storage."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    """Localhost user profile (Student via ID, Lecturer via ID + password)."""

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    password_hash: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_approved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    @property
    def id_number(self) -> str:
        """Alias user_id as id_number for login/API compatibility."""
        return self.user_id


class Student(Base):
    """Students registry referenced by attendance and timed quiz submissions."""

    __tablename__ = "students"

    student_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    full_name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(back_populates="student")


class Course(Base):
    """Academic course managed by a lecturer."""

    __tablename__ = "courses"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    lecturer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class Enrollment(Base):
    """Student course enrollment request ('pending' or 'approved')."""

    __tablename__ = "enrollments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), nullable=False)
    course_id: Mapped[str] = mapped_column(ForeignKey("courses.id"), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")
    enrolled_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class LectureSession(Base):
    """Live or recorded classroom lecture session."""

    __tablename__ = "sessions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    course_name: Mapped[str] = mapped_column(String(100), nullable=False)
    course_id: Mapped[Optional[str]] = mapped_column(ForeignKey("courses.id"), nullable=True)
    lecturer_id: Mapped[Optional[str]] = mapped_column(ForeignKey("users.user_id"), nullable=True)
    start_time: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    end_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    total_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_detected: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    students_left_early: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    attendance_records: Mapped[list["AttendanceRecord"]] = relationship(back_populates="session")
    polls: Mapped[list["Poll"]] = relationship(back_populates="session")


class AttendanceRecord(Base):
    """Visual attendance tracking log per ByteTrack track_id."""

    __tablename__ = "attendance_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    student_id: Mapped[Optional[str]] = mapped_column(ForeignKey("students.student_id"), nullable=True)
    dwell_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_eligible: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    session: Mapped["LectureSession"] = relationship(back_populates="attendance_records")
    student: Mapped[Optional["Student"]] = relationship(back_populates="attendance_records")


class QuizQuestion(Base):
    """Question bank imported from lecturer Excel (.xlsx) files."""

    __tablename__ = "quiz_questions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    question_text: Mapped[str] = mapped_column(Text, nullable=False)
    option_a: Mapped[str] = mapped_column(String(255), nullable=False)
    option_b: Mapped[str] = mapped_column(String(255), nullable=False)
    option_c: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    option_d: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    correct_option: Mapped[str] = mapped_column(String(2), nullable=False)
    is_used: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class ActiveQuestionToken(Base):
    """5-minute expiring token embedded in dynamic classroom QR codes."""

    __tablename__ = "active_question_tokens"

    token: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(ForeignKey("quiz_questions.id"), nullable=False)
    lecturer_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    question: Mapped["QuizQuestion"] = relationship()
    submissions: Mapped[list["QuizSubmission"]] = relationship(back_populates="token_ref")


class QuizSubmission(Base):
    """Student answer recorded during an active 5-minute QR window."""

    __tablename__ = "quiz_submissions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    token: Mapped[str] = mapped_column(ForeignKey("active_question_tokens.token"), nullable=False)
    student_id: Mapped[str] = mapped_column(ForeignKey("students.student_id"), nullable=False)
    selected_option: Mapped[str] = mapped_column(String(2), nullable=False)
    submitted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    is_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)

    token_ref: Mapped["ActiveQuestionToken"] = relationship(back_populates="submissions")


class Poll(Base):
    """Instant KISS in-class poll (2 to 4 options)."""

    __tablename__ = "polls"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    session_id: Mapped[str] = mapped_column(ForeignKey("sessions.id"), nullable=False)
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    option_1: Mapped[str] = mapped_column(String(100), nullable=False)
    option_2: Mapped[str] = mapped_column(String(100), nullable=False)
    option_3: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    option_4: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
    is_open: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    session: Mapped["LectureSession"] = relationship(back_populates="polls")
    votes: Mapped[list["PollVote"]] = relationship(back_populates="poll")


class PollVote(Base):
    """Individual vote submitted for an instant poll."""

    __tablename__ = "poll_votes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    poll_id: Mapped[str] = mapped_column(ForeignKey("polls.id"), nullable=False)
    student_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    selected_option: Mapped[str] = mapped_column(String(100), nullable=False)
    voted_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    poll: Mapped["Poll"] = relationship(back_populates="votes")


class ForumPost(Base):
    """Course discussion thread, AI summary post, or private student-lecturer message.

    Course-scoped threads set ``course_id`` and ``title``; legacy feed entries
    (AI summaries, private messages) leave both NULL.
    """

    __tablename__ = "forum_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    course_id: Mapped[Optional[str]] = mapped_column(
        ForeignKey("courses.id"), nullable=True, index=True
    )
    session_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    course_name: Mapped[str] = mapped_column(String(100), nullable=False, default="General")
    author_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    author_role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    post_type: Mapped[str] = mapped_column(String(30), nullable=False, default="question")
    recipient_id: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    comments: Mapped[list["ForumComment"]] = relationship(
        back_populates="post",
        order_by="ForumComment.created_at",
        cascade="all, delete-orphan",
    )


class ForumComment(Base):
    """Reply attached to a course discussion thread."""

    __tablename__ = "forum_comments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    post_id: Mapped[int] = mapped_column(
        ForeignKey("forum_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[str] = mapped_column(String(20), nullable=False)
    author_name: Mapped[str] = mapped_column(String(100), nullable=False)
    author_role: Mapped[str] = mapped_column(String(20), nullable=False, default="student")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)

    post: Mapped["ForumPost"] = relationship(back_populates="comments")


class LectureSummary(Base):
    """AI-generated summary extracted from a lecture recording or transcript."""

    __tablename__ = "lecture_summaries"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    transcript: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    markdown_summary: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)


class HomeworkReview(Base):
    """AI-generated OOD/SOLID evaluation and cross-student comparative feedback."""

    __tablename__ = "homework_reviews"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    session_id: Mapped[Optional[str]] = mapped_column(ForeignKey("sessions.id"), nullable=True)
    submission_label: Mapped[str] = mapped_column(String(100), nullable=False)
    repo_url: Mapped[str] = mapped_column(String(500), nullable=False)
    score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    ood_feedback: Mapped[str] = mapped_column(Text, nullable=False)
    comparative_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, default=utcnow)
