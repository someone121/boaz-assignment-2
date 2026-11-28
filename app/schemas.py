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


class CourseLecturerUpdate(BaseModel):
    """Reassign a course to another lecturer."""

    acting_lecturer_id: str = Field(..., min_length=1, max_length=20)
    lecturer_id: str = Field(..., min_length=1, max_length=20)


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
    no_data: bool = False
    is_mock_data: bool = False


class CheckInTriggerRequest(BaseModel):
    """Trigger a short-lived attendance self check-in QR."""

    session_id: str
    lecturer_id: Optional[str] = None
    ttl_seconds: int = Field(default=300, ge=30, le=3600)


class CheckInSubmitRequest(BaseModel):
    """Student self check-in submission."""

    token: str
    student_id: str = Field(..., min_length=2, max_length=20)
    full_name: str = Field(..., min_length=1, max_length=100)


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
    course_id: Optional[str] = None
    session_id: Optional[str] = None
    course_name: str
    author_id: Optional[str] = None
    author_name: str
    author_role: str
    post_type: str
    recipient_id: Optional[str] = None
    title: Optional[str] = None
    content: str
    is_read: bool = False
    created_at: datetime


class CoursePostCreate(BaseModel):
    """Create a new discussion thread inside a course forum."""

    author_id: str = Field(..., min_length=1, max_length=20)
    title: str = Field(..., min_length=1, max_length=200)
    content: str = Field(..., min_length=1, max_length=10000)


class ForumCommentCreate(BaseModel):
    """Add a reply to a course discussion thread."""

    author_id: str = Field(..., min_length=1, max_length=20)
    content: str = Field(..., min_length=1, max_length=5000)


class ForumCommentResponse(BaseModel):
    """Serialized reply on a course discussion thread."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    post_id: int
    author_id: str
    author_name: str
    author_role: str
    content: str
    created_at: datetime


class CoursePostResponse(BaseModel):
    """Serialized course discussion thread with its nested replies."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    course_id: str
    author_id: Optional[str] = None
    author_name: str
    author_role: str
    title: str
    content: str
    created_at: datetime
    comments: list[ForumCommentResponse] = []


class HomeworkReviewRequest(BaseModel):
    """Submit repository URLs for comparative AI OOD/SOLID review."""

    session_id: Optional[str] = None
    student_id: Optional[str] = None
    repo_urls: list[str] = Field(..., min_length=1)
