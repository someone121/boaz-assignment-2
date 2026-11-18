"""Unit tests for 5-minute (300s) timed quiz token expiry validation."""

from datetime import datetime, timedelta

from app.services.quiz_service import TimedTokenManager


def test_token_valid_at_299_seconds():
    """Token remains valid at 299 seconds after issuance."""
    manager = TimedTokenManager(ttl_seconds=300)
    issued_at = datetime(2026, 11, 17, 10, 0, 0)
    token_row = manager.build_token_record(session_id="s1", question_id=1, now=issued_at)

    assert manager.is_valid(token_row, now=issued_at + timedelta(seconds=299)) is True


def test_token_invalid_at_301_seconds():
    """Token expires strictly after 300 seconds."""
    manager = TimedTokenManager(ttl_seconds=300)
    issued_at = datetime(2026, 11, 17, 10, 0, 0)
    token_row = manager.build_token_record(session_id="s1", question_id=1, now=issued_at)

    assert manager.is_valid(token_row, now=issued_at + timedelta(seconds=301)) is False
