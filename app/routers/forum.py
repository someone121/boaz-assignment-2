"""Class Q&A / blog feed and private lecturer-student message endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import ForumPost, utcnow
from app.schemas import ForumPostCreate, ForumPostResponse
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/forum", tags=["Forum"])


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
    if payload.post_type != "private_message":
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
