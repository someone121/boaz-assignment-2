"""Instant KISS polling endpoints."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Poll
from app.schemas import PollCreateRequest, PollVoteRequest
from app.services import poll_service
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/poll", tags=["Polls"])


@router.post("/create")
async def create_live_poll(payload: PollCreateRequest, db: Session = Depends(get_db)) -> dict:
    """Broadcast a new 1-click KISS poll."""
    poll = poll_service.create_poll(db, payload)
    result = poll_service.get_poll_results(db, poll)
    await ws_manager.broadcast_event(
        poll.session_id,
        "POLL_UPDATE",
        {
            "poll_id": poll.id,
            "prompt": poll.prompt,
            "results": result["results"],
        },
    )
    return result


@router.get("/{session_id}")
def list_session_polls(session_id: str, db: Session = Depends(get_db)) -> list[dict]:
    """List all polls for a session along with current vote tallies."""
    polls = (
        db.query(Poll)
        .filter(Poll.session_id == session_id)
        .order_by(Poll.created_at.desc())
        .all()
    )
    return [poll_service.get_poll_results(db, poll) for poll in polls]


@router.post("/vote")
async def vote_in_poll(payload: PollVoteRequest, db: Session = Depends(get_db)) -> dict:
    """Submit a student vote and push live POLL_UPDATE counts."""
    result = poll_service.submit_vote(
        db=db,
        poll_id=payload.poll_id,
        selected_option=payload.selected_option,
        student_id=payload.student_id,
    )
    await ws_manager.broadcast_event(
        result["session_id"],
        "POLL_UPDATE",
        {
            "poll_id": result["poll_id"],
            "prompt": result["prompt"],
            "results": result["results"],
        },
    )
    return result
