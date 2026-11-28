"""AI lecture video summarization and comparative homework review endpoints."""

import json
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, UploadFile
from sqlalchemy.orm import Session

from app.config import UPLOADS_DIR
from app.database import get_db
from app.models import HomeworkReview, LectureSummary
from app.schemas import HomeworkReviewRequest
from app.services.ai_service import ai_service
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/ai", tags=["AI"])


def _serialize_review(r: HomeworkReview) -> dict:
    return {
        "id": r.id,
        "session_id": r.session_id,
        "student_id": r.student_id,
        "submission_label": r.submission_label,
        "repo_url": r.repo_url,
        "score": r.score,
        "ood_feedback": r.ood_feedback,
        "comparative_notes": r.comparative_notes,
        "rubric": json.loads(r.rubric_json) if r.rubric_json else {},
        "similarity": json.loads(r.similarity_json) if r.similarity_json else {},
        "analysis_mode": r.analysis_mode,
        "created_at": r.created_at.isoformat(),
    }


@router.post("/summarize-lecture")
async def summarize_lecture_recording(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(default=None),
    course_name: str = Form(default="Course Forum"),
    course_id: Optional[str] = Form(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """Upload a lecture recording/transcript, generate AI summary, and publish to forum."""
    UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
    filename = file.filename or "lecture_recording.mp4"
    saved_path = UPLOADS_DIR / filename
    saved_path.write_bytes(await file.read())

    summary, forum_post = ai_service.summarize_lecture(
        db=db,
        filename=filename,
        file_path=saved_path,
        session_id=session_id,
        course_name=course_name,
        course_id=course_id,
    )

    target_channel = session_id or "global"
    await ws_manager.broadcast_event(
        target_channel,
        "SUMMARY_READY",
        {
            "session_id": target_channel,
            "markdown_summary": summary.markdown_summary,
            "transcription_available": getattr(summary, "_transcription_available", True),
            "source_mode": getattr(summary, "_source_mode", "text"),
        },
    )

    if forum_post.course_id:
        await ws_manager.broadcast_event(
            f"course:{forum_post.course_id}",
            "FORUM_THREAD_NEW",
            {
                "id": forum_post.id,
                "course_id": forum_post.course_id,
                "author_id": forum_post.author_id,
                "author_name": forum_post.author_name,
                "author_role": forum_post.author_role,
                "title": forum_post.title,
                "content": forum_post.content,
                "created_at": forum_post.created_at.isoformat(),
                "comments": [],
            },
        )
    else:
        await ws_manager.broadcast_event(
            target_channel,
            "NEW_FORUM_POST",
            {
                "id": forum_post.id,
                "author": forum_post.author_name,
                "author_role": forum_post.author_role,
                "post_type": forum_post.post_type,
                "content": forum_post.content,
                "timestamp": forum_post.created_at.isoformat(),
            },
        )

    return {
        "summary_id": summary.id,
        "forum_post_id": forum_post.id,
        "course_id": forum_post.course_id,
        "filename": summary.filename,
        "markdown_summary": summary.markdown_summary,
        "transcription_available": getattr(summary, "_transcription_available", True),
        "source_mode": getattr(summary, "_source_mode", "text"),
    }


@router.get("/summaries")
def list_lecture_summaries(db: Session = Depends(get_db)) -> list[dict]:
    """Return previously generated AI lecture summaries."""
    summaries = db.query(LectureSummary).order_by(LectureSummary.created_at.desc()).all()
    return [
        {
            "id": s.id,
            "session_id": s.session_id,
            "filename": s.filename,
            "markdown_summary": s.markdown_summary,
            "created_at": s.created_at.isoformat(),
        }
        for s in summaries
    ]


@router.post("/review-homework")
def review_homework_submissions(
    payload: HomeworkReviewRequest, db: Session = Depends(get_db)
) -> dict:
    """Evaluate student repository URLs for OOD/SOLID quality and cross-compare."""
    reviews = ai_service.review_homework(
        db=db,
        repo_urls=payload.repo_urls,
        session_id=payload.session_id,
        student_id=payload.student_id,
    )
    return {
        "count": len(reviews),
        "reviews": [_serialize_review(r) for r in reviews],
    }


@router.get("/reviews")
def list_homework_reviews(
    student_id: Optional[str] = None, db: Session = Depends(get_db)
) -> list[dict]:
    """List stored AI homework reviews, optionally filtered by student_id."""
    query = db.query(HomeworkReview)
    if student_id:
        query = query.filter(HomeworkReview.student_id == student_id)
    reviews = query.order_by(HomeworkReview.created_at.desc()).all()
    return [_serialize_review(r) for r in reviews]
