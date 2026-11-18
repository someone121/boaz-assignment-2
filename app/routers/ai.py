"""AI lecture video summarization and comparative homework review endpoints."""

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


@router.post("/summarize-lecture")
async def summarize_lecture_recording(
    file: UploadFile = File(...),
    session_id: Optional[str] = Form(default=None),
    course_name: str = Form(default="Course Forum"),
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
    )

    target_channel = session_id or "global"
    await ws_manager.broadcast_event(
        target_channel,
        "SUMMARY_READY",
        {
            "session_id": target_channel,
            "markdown_summary": summary.markdown_summary,
        },
    )
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
        "filename": summary.filename,
        "markdown_summary": summary.markdown_summary,
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
    )
    return {
        "count": len(reviews),
        "reviews": [
            {
                "id": r.id,
                "submission_label": r.submission_label,
                "repo_url": r.repo_url,
                "score": r.score,
                "ood_feedback": r.ood_feedback,
                "comparative_notes": r.comparative_notes,
            }
            for r in reviews
        ],
    }


@router.get("/reviews")
def list_homework_reviews(db: Session = Depends(get_db)) -> list[dict]:
    """List stored AI homework reviews."""
    reviews = db.query(HomeworkReview).order_by(HomeworkReview.created_at.desc()).all()
    return [
        {
            "id": r.id,
            "session_id": r.session_id,
            "submission_label": r.submission_label,
            "repo_url": r.repo_url,
            "score": r.score,
            "ood_feedback": r.ood_feedback,
            "comparative_notes": r.comparative_notes,
            "created_at": r.created_at.isoformat(),
        }
        for r in reviews
    ]
