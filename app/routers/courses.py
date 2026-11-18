"""Course catalog and student enrollment workflow endpoints."""

from typing import Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Course, Enrollment, Student, User, utcnow
from app.schemas import (
    CourseCreate,
    CourseResponse,
    EnrollApproveRequest,
    EnrollmentResponse,
    EnrollRequest,
)

router = APIRouter(prefix="/api", tags=["Courses & Enrollment"])


@router.get("/courses", response_model=list[CourseResponse])
def list_courses(student_id: Optional[str] = None, db: Session = Depends(get_db)) -> list[CourseResponse]:
    """List all courses, optionally enriched with a student's enrollment status."""
    courses = db.query(Course).order_by(Course.created_at.desc()).all()
    enrollments_by_course: dict[str, str] = {}
    if student_id:
        student_enrollments = (
            db.query(Enrollment).filter(Enrollment.student_id == student_id).all()
        )
        enrollments_by_course = {e.course_id: e.status for e in student_enrollments}

    result: list[CourseResponse] = []
    for course in courses:
        lecturer = db.get(User, course.lecturer_id) if course.lecturer_id else None
        result.append(
            CourseResponse(
                id=course.id,
                name=course.name,
                lecturer_id=course.lecturer_id,
                lecturer_name=lecturer.full_name if lecturer else "Course Instructor",
                enrollment_status=enrollments_by_course.get(course.id),
                created_at=course.created_at,
            )
        )
    return result


@router.post("/courses", response_model=CourseResponse)
def create_course(payload: CourseCreate, db: Session = Depends(get_db)) -> CourseResponse:
    """Allow a lecturer to create a new course."""
    course = Course(
        id=str(uuid.uuid4()),
        name=payload.name.strip(),
        lecturer_id=payload.lecturer_id,
        created_at=utcnow(),
    )
    db.add(course)
    db.commit()
    db.refresh(course)
    lecturer = db.get(User, course.lecturer_id) if course.lecturer_id else None
    return CourseResponse(
        id=course.id,
        name=course.name,
        lecturer_id=course.lecturer_id,
        lecturer_name=lecturer.full_name if lecturer else "Course Instructor",
        enrollment_status=None,
        created_at=course.created_at,
    )


@router.post("/enroll", response_model=EnrollmentResponse)
def request_enrollment(payload: EnrollRequest, db: Session = Depends(get_db)) -> EnrollmentResponse:
    """Student requests to join a course (creates a 'pending' enrollment)."""
    course = db.get(Course, payload.course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")

    student = db.get(Student, payload.student_id)
    if student is None:
        user = db.get(User, payload.student_id)
        student = Student(
            student_id=payload.student_id,
            full_name=user.full_name if user else f"Student {payload.student_id}",
        )
        db.add(student)
        db.flush()

    existing = (
        db.query(Enrollment)
        .filter(
            Enrollment.student_id == payload.student_id,
            Enrollment.course_id == payload.course_id,
        )
        .first()
    )
    if existing is not None:
        return EnrollmentResponse(
            id=existing.id,
            student_id=existing.student_id,
            student_name=student.full_name,
            course_id=course.id,
            course_name=course.name,
            status=existing.status,
            enrolled_at=existing.enrolled_at,
        )

    enrollment = Enrollment(
        student_id=payload.student_id,
        course_id=payload.course_id,
        status="pending",
        enrolled_at=utcnow(),
    )
    db.add(enrollment)
    db.commit()
    db.refresh(enrollment)

    return EnrollmentResponse(
        id=enrollment.id,
        student_id=enrollment.student_id,
        student_name=student.full_name,
        course_id=course.id,
        course_name=course.name,
        status=enrollment.status,
        enrolled_at=enrollment.enrolled_at,
    )


@router.get("/enroll/pending", response_model=list[EnrollmentResponse])
def list_pending_enrollments(db: Session = Depends(get_db)) -> list[EnrollmentResponse]:
    """List all pending student enrollment requests for lecturer approval."""
    pending = (
        db.query(Enrollment)
        .filter(Enrollment.status == "pending")
        .order_by(Enrollment.enrolled_at.desc())
        .all()
    )
    items: list[EnrollmentResponse] = []
    for enr in pending:
        student = db.get(Student, enr.student_id)
        course = db.get(Course, enr.course_id)
        items.append(
            EnrollmentResponse(
                id=enr.id,
                student_id=enr.student_id,
                student_name=student.full_name if student else enr.student_id,
                course_id=enr.course_id,
                course_name=course.name if course else enr.course_id,
                status=enr.status,
                enrolled_at=enr.enrolled_at,
            )
        )
    return items


@router.post("/enroll/approve", response_model=EnrollmentResponse)
def approve_enrollment(
    payload: EnrollApproveRequest, db: Session = Depends(get_db)
) -> EnrollmentResponse:
    """Lecturer approves a student's pending enrollment request."""
    enrollment: Optional[Enrollment] = None
    if payload.enrollment_id is not None:
        enrollment = db.get(Enrollment, payload.enrollment_id)
    elif payload.student_id and payload.course_id:
        enrollment = (
            db.query(Enrollment)
            .filter(
                Enrollment.student_id == payload.student_id,
                Enrollment.course_id == payload.course_id,
            )
            .first()
        )
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide enrollment_id or both student_id and course_id.",
        )

    if enrollment is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Enrollment request not found.")

    enrollment.status = "approved"
    db.commit()
    db.refresh(enrollment)

    student = db.get(Student, enrollment.student_id)
    course = db.get(Course, enrollment.course_id)
    return EnrollmentResponse(
        id=enrollment.id,
        student_id=enrollment.student_id,
        student_name=student.full_name if student else enrollment.student_id,
        course_id=enrollment.course_id,
        course_name=course.name if course else enrollment.course_id,
        status=enrollment.status,
        enrolled_at=enrollment.enrolled_at,
    )
