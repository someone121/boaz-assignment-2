"""Unit tests for PresencePolicy boundary conditions."""

from app.services.attendance_service import FixedTimePresencePolicy, PercentagePresencePolicy


def test_presence_eligible():
    """Student present for >= 70% of session duration is marked eligible."""
    policy = PercentagePresencePolicy(threshold_ratio=0.70)
    assert policy.is_eligible(dwell_seconds=700, session_total_seconds=1000) is True
    assert policy.is_eligible(dwell_seconds=850, session_total_seconds=1000) is True


def test_presence_below_threshold():
    """Student present for 69.9% of session duration is marked not eligible."""
    policy = PercentagePresencePolicy(threshold_ratio=0.70)
    assert policy.is_eligible(dwell_seconds=699, session_total_seconds=1000) is False


def test_fixed_time_presence_policy():
    """Fixed-time policy requires at least the configured minutes of dwell time."""
    policy = FixedTimePresencePolicy(required_minutes=45)
    assert policy.is_eligible(dwell_seconds=45 * 60, session_total_seconds=5400) is True
    assert policy.is_eligible(dwell_seconds=44 * 60 + 59, session_total_seconds=5400) is False
