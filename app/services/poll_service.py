"""Instant KISS live polling service."""

import uuid

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.models import Poll, PollVote, utcnow
from app.schemas import PollCreateRequest


def create_poll(db: Session, payload: PollCreateRequest) -> Poll:
    """Create and persist a new 2-to-4 option KISS poll."""
    poll = Poll(
        id=str(uuid.uuid4()),
        session_id=payload.session_id,
        prompt=payload.prompt,
        option_1=payload.option_1,
        option_2=payload.option_2,
        option_3=payload.option_3,
        option_4=payload.option_4,
        created_at=utcnow(),
        is_open=True,
    )
    db.add(poll)
    db.commit()
    db.refresh(poll)
    return poll


def get_poll_results(db: Session, poll: Poll) -> dict:
    """Aggregate live vote counts for each configured poll option."""
    options = [
        opt for opt in (poll.option_1, poll.option_2, poll.option_3, poll.option_4) if opt
    ]
    counts = {opt: 0 for opt in options}
    votes = db.query(PollVote).filter(PollVote.poll_id == poll.id).all()
    for vote in votes:
        if vote.selected_option in counts:
            counts[vote.selected_option] += 1

    return {
        "poll_id": poll.id,
        "session_id": poll.session_id,
        "prompt": poll.prompt,
        "options": options,
        "results": counts,
        "total_votes": len(votes),
        "is_open": poll.is_open,
    }


def submit_vote(db: Session, poll_id: str, selected_option: str, student_id: str | None = None) -> dict:
    """Record a vote on an open poll and return updated counts."""
    poll = db.get(Poll, poll_id)
    if poll is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Poll not found.")
    if not poll.is_open:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Poll is closed.")

    valid_options = {
        opt for opt in (poll.option_1, poll.option_2, poll.option_3, poll.option_4) if opt
    }
    if selected_option not in valid_options:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Selected option is not valid for this poll.",
        )

    vote = PollVote(
        poll_id=poll_id,
        student_id=student_id,
        selected_option=selected_option,
        voted_at=utcnow(),
    )
    db.add(vote)
    db.commit()
    return get_poll_results(db, poll)
