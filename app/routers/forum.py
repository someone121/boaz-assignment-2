"""Class forum endpoints.

Two groups of routes live here:

* Course-scoped discussion threads + replies (plain REST, no WebSockets):
    GET  /api/courses/{course_id}/posts
    POST /api/courses/{course_id}/posts
    POST /api/posts/{post_id}/comments
  Only the course's lecturer or students with an 'approved' enrollment may
  read or write. The caller's role is always resolved from the users table,
  never trusted from the request body.

* Legacy global feed (AI summaries, private messages) under /api/forum.
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, selectinload

from app.database import get_db
from app.models import Course, Enrollment, ForumComment, ForumPost, User, utcnow
from app.schemas import (
    CoursePostCreate,
    CoursePostResponse,
    ForumCommentCreate,
    ForumCommentResponse,
    ForumPostCreate,
    ForumPostResponse,
)
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/forum", tags=["Forum"])
course_forum_router = APIRouter(prefix="/api", tags=["Course Forum"])


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def _get_user_or_401(db: Session, user_id: str) -> User:
    """Resolve the acting user from the database."""
    user = db.get(User, (user_id or "").strip())
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Unknown user. Please log in again.",
        )
    return user


def _user_can_access_course(db: Session, user: User, course: Course) -> bool:
    """Lecturers must teach the course; students must hold an approved enrollment."""
    if user.role == "lecturer":
        return course.lecturer_id == user.user_id
    if user.role == "student":
        return (
            db.query(Enrollment.id)
            .filter(
                Enrollment.student_id == user.user_id,
                Enrollment.course_id == course.id,
                Enrollment.status == "approved",
            )
            .first()
            is not None
        )
    return False


def _require_course_access(db: Session, course_id: str, user_id: str) -> tuple[Course, User]:
    """Return (course, user) or raise 404 / 401 / 403."""
    course = db.get(Course, course_id)
    if course is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Course not found.")
    user = _get_user_or_401(db, user_id)
    if not _user_can_access_course(db, user, course):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You must teach this course or be an approved student to use its forum.",
        )
    return course, user


# ---------------------------------------------------------------------------
# Course-scoped discussion threads (REST)
# ---------------------------------------------------------------------------


@course_forum_router.get("/courses/{course_id}/posts", response_model=list[CoursePostResponse])
def list_course_posts(
    course_id: str,
    user_id: str = Query(..., min_length=1, description="ID of the logged-in user"),
    db: Session = Depends(get_db),
) -> list[ForumPost]:
    """Return a course's threads (newest first) with their replies (oldest first)."""
    _require_course_access(db, course_id, user_id)
    return (
        db.query(ForumPost)
        .options(selectinload(ForumPost.comments))
        .filter(ForumPost.course_id == course_id)
        .order_by(ForumPost.created_at.desc(), ForumPost.id.desc())
        .all()
    )


@course_forum_router.post(
    "/courses/{course_id}/posts",
    response_model=CoursePostResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_course_post(
    course_id: str, payload: CoursePostCreate, db: Session = Depends(get_db)
) -> ForumPost:
    """Start a new discussion thread in a course and broadcast FORUM_THREAD_NEW."""
    course, user = _require_course_access(db, course_id, payload.author_id)

    title = payload.title.strip()
    content = payload.content.strip()
    if not title or not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Title and content cannot be empty.",
        )

    post = ForumPost(
        course_id=course.id,
        course_name=course.name[:100],
        author_id=user.user_id,
        author_name=user.full_name,
        author_role=user.role,
        post_type="discussion",
        title=title,
        content=content,
        created_at=utcnow(),
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    await ws_manager.broadcast_event(
        f"course:{course.id}",
        "FORUM_THREAD_NEW",
        {
            "id": post.id,
            "course_id": post.course_id,
            "author_id": post.author_id,
            "author_name": post.author_name,
            "author_role": post.author_role,
            "title": post.title,
            "content": post.content,
            "created_at": post.created_at.isoformat(),
            "comments": [],
        },
    )
    return post


@course_forum_router.post(
    "/posts/{post_id}/comments",
    response_model=ForumCommentResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_post_comment(
    post_id: int, payload: ForumCommentCreate, db: Session = Depends(get_db)
) -> ForumComment:
    """Reply to a course discussion thread and broadcast FORUM_COMMENT_NEW."""
    post = db.get(ForumPost, post_id)
    if post is None or post.course_id is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")

    _, user = _require_course_access(db, post.course_id, payload.author_id)

    content = payload.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Reply cannot be empty.",
        )

    comment = ForumComment(
        post_id=post.id,
        author_id=user.user_id,
        author_name=user.full_name,
        author_role=user.role,
        content=content,
        created_at=utcnow(),
    )
    db.add(comment)
    db.commit()
    db.refresh(comment)

    await ws_manager.broadcast_event(
        f"course:{post.course_id}",
        "FORUM_COMMENT_NEW",
        {
            "post_id": post.id,
            "course_id": post.course_id,
            "comment": {
                "id": comment.id,
                "post_id": comment.post_id,
                "author_id": comment.author_id,
                "author_name": comment.author_name,
                "author_role": comment.author_role,
                "content": comment.content,
                "created_at": comment.created_at.isoformat(),
            },
        },
    )
    return comment


# ---------------------------------------------------------------------------
# Legacy global feed (AI summaries, private messages)
# ---------------------------------------------------------------------------


@router.get("/posts", response_model=list[ForumPostResponse])
def list_forum_posts(
    session_id: Optional[str] = None,
    post_type: Optional[str] = None,
    db: Session = Depends(get_db),
) -> list[ForumPost]:
    """Retrieve class Q&A posts, AI summaries, or private messages newest first."""
    query = db.query(ForumPost)
    if session_id:
        query = query.filter(ForumPost.session_id == session_id)
    if post_type:
        query = query.filter(ForumPost.post_type == post_type)
    return query.order_by(ForumPost.created_at.desc(), ForumPost.id.desc()).all()


@router.post("/posts", response_model=ForumPostResponse)
async def create_forum_post(payload: ForumPostCreate, db: Session = Depends(get_db)) -> ForumPost:
    """Create a forum post and broadcast NEW_FORUM_POST to connected clients."""
    post = ForumPost(
        session_id=payload.session_id,
        course_name=payload.course_name,
        author_id=payload.author_id,
        author_name=payload.author_name,
        author_role=payload.author_role,
        post_type=payload.post_type,
        recipient_id=payload.recipient_id,
        content=payload.content,
        created_at=utcnow(),
    )
    db.add(post)
    db.commit()
    db.refresh(post)

    target_channel = payload.session_id or "global"
    if payload.post_type == "private_message":
        await ws_manager.broadcast_event(
            target_channel,
            "STUDENT_MESSAGE_NEW",
            {
                "id": post.id,
                "author_id": post.author_id,
                "author_name": post.author_name,
                "content": post.content,
                "is_read": post.is_read,
                "created_at": post.created_at.isoformat(),
            },
        )
    else:
        await ws_manager.broadcast_event(
            target_channel,
            "NEW_FORUM_POST",
            {
                "id": post.id,
                "author": post.author_name,
                "author_role": post.author_role,
                "post_type": post.post_type,
                "content": post.content,
                "timestamp": post.created_at.isoformat(),
            },
        )
    return post


@router.post("/posts/{post_id}/read", response_model=ForumPostResponse)
def mark_post_as_read(post_id: int, db: Session = Depends(get_db)) -> ForumPost:
    """Mark a student private message/suggestion as read."""
    post = db.get(ForumPost, post_id)
    if post is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Post not found.")
    post.is_read = True
    db.commit()
    db.refresh(post)
    return post
