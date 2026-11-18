"""Pydantic v2 request and response schemas for SmartClass AI."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class LoginRequest(BaseModel):
    """Localhost profile login/registration payload."""

    id_number: Optional[str] = Field(default=None, min_length=2, max_length=20)
    user_id: Optional[str] = Field(default=None, min_length=2, max_length=20)
    full_name: Optional[str] = Field(default=None, max_length=100)
    role: Optional[Literal["student", "lecturer"]] = None
    password: Optional[str] = None
    email: Optional[str] = None


class UserResponse(BaseModel):
    """Serialized user profile."""

    model_config = ConfigDict(from_attributes=True)

    id_number: str
    user_id: str
    full_name: str
    email: Optional[str] = None
    role: str
    is_approved: bool
    created_at: datetime


class CourseCreate(BaseModel):
    """Create a new course."""

    name: str = Field(..., min_length=1, max_length=100)
    lecturer_id: Optional[str] = None


class CourseResponse(BaseModel):
    """Serialized course with optional student enrollment status."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    lecturer_id: Optional[str] = None
    lecturer_name: Optional[str] = None
    enrollment_status: Optional[str] = None
    created_at: datetime


class EnrollRequest(BaseModel):
    """Student request to join a course."""

    student_id: str = Field(..., min_length=2, max_length=20)
    course_id: str


class EnrollApproveRequest(BaseModel):
    """Lecturer approval of a pending student enrollment."""

    enrollment_id: Optional[int] = None
    student_id: Optional[str] = None
    course_id: Optional[str] = None


class EnrollmentResponse(BaseModel):
    """Serialized course enrollment entry."""

    id: int
    student_id: str
    student_name: str
    course_id: str
    course_name: str
    status: str
    enrolled_at: datetime


class SessionStartRequest(BaseModel):
    """Start a new classroom lecture session."""

    course_name: str = Field(..., min_length=1, max_length=100)
    course_id: Optional[str] = None
    lecturer_id: Optional[str] = None


class SessionResponse(BaseModel):
    """Serialized lecture session."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    course_name: str
    course_id: Optional[str] = None
    lecturer_id: Optional[str] = None
    start_time: datetime
    end_time: Optional[datetime] = None
    total_duration_minutes: int
    total_detected: int = 0
    students_left_early: int = 0
    is_active: bool


class SessionReportResponse(BaseModel):
    """Post-recording or end-of-class attendance summary report."""

    session_id: str
    course_name: str
    is_active: bool
    total_duration_minutes: int
    total_detected: int
    students_left_early: int
    total_present: int
    attendance_rate_percent: float
    is_mock_data: bool = False


class QuizTriggerRequest(BaseModel):
    """Trigger a 5-minute timed quiz question."""

    session_id: str
    question_id: Optional[int] = None
    lecturer_id: Optional[str] = None


class QuizSubmitRequest(BaseModel):
    """Student submission for an active 5-minute QR token."""

    token: str
    student_id: str = Field(..., min_length=2, max_length=20)
    full_name: str = Field(..., min_length=1, max_length=100)
    selected_option: str = Field(..., min_length=1, max_length=2)


class PollCreateRequest(BaseModel):
    """Create an instant KISS poll."""

    session_id: str
    prompt: str = Field(..., min_length=1)
    option_1: str = Field(..., min_length=1, max_length=100)
    option_2: str = Field(..., min_length=1, max_length=100)
    option_3: Optional[str] = Field(default=None, max_length=100)
    option_4: Optional[str] = Field(default=None, max_length=100)


class PollVoteRequest(BaseModel):
    """Submit a vote to an open poll."""

    poll_id: str
    selected_option: str = Field(..., min_length=1, max_length=100)
    student_id: Optional[str] = None


class ForumPostCreate(BaseModel):
    """Create a class forum post or private lecturer-student message."""

    session_id: Optional[str] = None
    course_name: str = "General"
    author_id: Optional[str] = None
    author_name: str = Field(..., min_length=1, max_length=100)
    author_role: Literal["student", "lecturer", "ai"] = "student"
    post_type: Literal["question", "note", "ai_summary", "private_message"] = "question"
    recipient_id: Optional[str] = None
    content: str = Field(..., min_length=1)


class ForumPostResponse(BaseModel):
    """Serialized forum post."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    session_id: Optional[str] = None
    course_name: str
    author_id: Optional[str] = None
    author_name: str
    author_role: str
    post_type: str
    recipient_id: Optional[str] = None
    content: str
    created_at: datetime


class HomeworkReviewRequest(BaseModel):
    """Submit repository URLs for comparative AI OOD/SOLID review."""

    session_id: Optional[str] = None
    repo_urls: list[str] = Field(..., min_length=1)
