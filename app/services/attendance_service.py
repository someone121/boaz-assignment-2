"""Automated visual attendance service with Strategy-pattern PresencePolicy and mock YOLO tracking."""

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
from sqlalchemy.orm import Session

from app.config import REPORTS_DIR, settings
from app.models import AttendanceRecord, LectureSession, Student, utcnow


class PresencePolicy(ABC):
    """Strategy interface for determining student attendance eligibility."""

    @abstractmethod
    def is_eligible(self, dwell_seconds: int, session_total_seconds: int) -> bool:
        """Return True when tracked dwell time satisfies attendance rules."""


class PercentagePresencePolicy(PresencePolicy):
    """Marks a student Present when dwell ratio meets or exceeds threshold_ratio."""

    def __init__(self, threshold_ratio: float = settings.DEFAULT_PRESENCE_THRESHOLD) -> None:
        self.threshold_ratio = threshold_ratio

    def is_eligible(self, dwell_seconds: int, session_total_seconds: int) -> bool:
        if session_total_seconds <= 0:
            return dwell_seconds > 0
        return (dwell_seconds / session_total_seconds) >= self.threshold_ratio


class FixedTimePresencePolicy(PresencePolicy):
    """Marks a student Present when total dwell time reaches required_minutes."""

    def __init__(self, required_minutes: int = 45) -> None:
        self.required_seconds = required_minutes * 60

    def is_eligible(self, dwell_seconds: int, session_total_seconds: int) -> bool:
        return dwell_seconds >= self.required_seconds


class TrackedPerson:
    """In-memory ByteTrack trajectory state for a detected person."""

    def __init__(self, track_id: int, student_id: Optional[str] = None) -> None:
        self.track_id = track_id
        self.first_seen = datetime.now(timezone.utc)
        self.last_seen = self.first_seen
        self.total_dwell_seconds = 0
        self.student_id = student_id

    def update_presence(self, elapsed_seconds: int) -> None:
        """Accumulate observed dwell seconds for this track."""
        self.last_seen = datetime.now(timezone.utc)
        self.total_dwell_seconds += max(0, elapsed_seconds)


class VisionTracker:
    """YOLOv8n + ByteTrack person tracker with automatic fallback when CV deps are absent."""

    def __init__(self, model_name: str = "yolov8n.pt") -> None:
        self.model_name = model_name
        self._model = None
        self._cv2 = None
        self._np = None
        self._initialized = False
        self.mode = "mock_yolo_bytetrack"

    def _lazy_load(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        try:
            import cv2
            import numpy as np
            from ultralytics import YOLO

            self._cv2 = cv2
            self._np = np
            self._model = YOLO(self.model_name)
            self.mode = "yolov8n_bytetrack"
        except Exception:
            # Keep mock tracker active when ultralytics/opencv are not installed.
            self._model = None
            self.mode = "mock_yolo_bytetrack"

    def detect_tracks(self, frame_bytes: bytes, filename: str = "") -> list[int]:
        """Run YOLOv8n + ByteTrack on an image/video frame, or simulate tracks in mock mode."""
        self._lazy_load()
        if self._model is not None and self._cv2 is not None and self._np is not None:
            buf = self._np.frombuffer(frame_bytes, dtype=self._np.uint8)
            image = self._cv2.imdecode(buf, self._cv2.IMREAD_COLOR)
            if image is not None:
                results = self._model.track(
                    image,
                    persist=True,
                    tracker="bytetrack.yaml",
                    classes=[0],
                    verbose=False,
                )
                track_ids: list[int] = []
                if results and results[0].boxes is not None and results[0].boxes.id is not None:
                    track_ids = [int(tid) for tid in results[0].boxes.id.tolist()]
                return track_ids

        seed = (len(frame_bytes) + len(filename)) % 5
        count = 3 + seed
        return list(range(1, count + 1))


class AttendanceManager:
    """Coordinates active visual tracking sessions, dwell accumulation, and CSV/Excel export."""

    def __init__(self, policy: Optional[PresencePolicy] = None) -> None:
        self.policy: PresencePolicy = policy or PercentagePresencePolicy()
        self.tracker = VisionTracker()
        self.active_sessions: dict[str, dict[int, TrackedPerson]] = {}
        self.session_starts: dict[str, datetime] = {}

    def ensure_session(self, session_id: str) -> None:
        """Initialize in-memory tracking buffers for a lecture session."""
        if session_id not in self.active_sessions:
            self.active_sessions[session_id] = {}
            self.session_starts[session_id] = datetime.now(timezone.utc)

    def process_frame(
        self,
        db: Session,
        session_id: str,
        frame_bytes: bytes,
        filename: str = "",
        interval_seconds: int = 5,
    ) -> dict:
        """Process a classroom frame/video chunk, update dwell times, and persist records."""
        self.ensure_session(session_id)
        detected_track_ids = self.tracker.detect_tracks(frame_bytes, filename)
        tracks = self.active_sessions[session_id]

        session_start = self.session_starts[session_id]
        session_total_seconds = max(
            interval_seconds,
            int((datetime.now(timezone.utc) - session_start).total_seconds()) + interval_seconds,
        )

        for track_id in detected_track_ids:
            if track_id not in tracks:
                tracks[track_id] = TrackedPerson(track_id=track_id)
            tracks[track_id].update_presence(interval_seconds)

            record = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.session_id == session_id,
                    AttendanceRecord.track_id == track_id,
                )
                .first()
            )
            dwell = tracks[track_id].total_dwell_seconds
            eligible = self.policy.is_eligible(dwell, session_total_seconds)
            if record is None:
                record = AttendanceRecord(
                    session_id=session_id,
                    track_id=track_id,
                    student_id=tracks[track_id].student_id,
                    dwell_seconds=dwell,
                    is_eligible=eligible,
                    last_seen_at=utcnow(),
                )
                db.add(record)
            else:
                record.dwell_seconds = dwell
                record.is_eligible = eligible
                record.last_seen_at = utcnow()

        db.commit()
        return {
            "session_id": session_id,
            "detected_count": len(detected_track_ids),
            "active_track_ids": detected_track_ids,
            "total_tracked_unique": len(tracks),
            "detector_mode": self.tracker.mode,
        }

    def link_student_to_session(self, db: Session, session_id: str, student_id: str) -> None:
        """Correlate a student ID (e.g., from 5-min QR submission) with an unassigned track."""
        unassigned = (
            db.query(AttendanceRecord)
            .filter(
                AttendanceRecord.session_id == session_id,
                AttendanceRecord.student_id.is_(None),
            )
            .first()
        )
        if unassigned is not None:
            unassigned.student_id = student_id
            db.commit()

    def evaluate_attendance(self, db: Session, session_id: str) -> list[dict]:
        """Compute attendance status rows for all tracks in a session."""
        lecture = db.get(LectureSession, session_id)
        records = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.session_id == session_id)
            .order_by(AttendanceRecord.track_id.asc())
            .all()
        )

        if lecture and lecture.end_time and lecture.start_time:
            total_seconds = max(1, int((lecture.end_time - lecture.start_time).total_seconds()))
        elif lecture and lecture.start_time:
            total_seconds = max(1, int((utcnow() - lecture.start_time).total_seconds()))
        else:
            total_seconds = max([r.dwell_seconds for r in records], default=1)

        report: list[dict] = []
        for rec in records:
            student = db.get(Student, rec.student_id) if rec.student_id else None
            is_present = self.policy.is_eligible(rec.dwell_seconds, total_seconds)
            rec.is_eligible = is_present
            report.append(
                {
                    "track_id": rec.track_id,
                    "student_id": rec.student_id or f"Track-{rec.track_id}",
                    "full_name": student.full_name if student else "Unassigned Student",
                    "dwell_seconds": rec.dwell_seconds,
                    "total_minutes_observed": round(rec.dwell_seconds / 60, 2),
                    "presence_status": "Present" if is_present else "Absent",
                }
            )
        db.commit()
        return report

    def stop_session(self, db: Session, session_id: str) -> dict:
        """Close an active lecture session and persist final attendance statistics."""
        rows = self.evaluate_attendance(db, session_id)
        present_count = sum(1 for row in rows if row["presence_status"] == "Present")
        total_detected = len(rows)
        left_early = max(0, total_detected - present_count)

        lecture = db.get(LectureSession, session_id)
        if lecture is not None:
            lecture.end_time = utcnow()
            lecture.is_active = False
            lecture.total_duration_minutes = max(
                1, int((lecture.end_time - lecture.start_time).total_seconds() // 60)
            )
            lecture.total_detected = total_detected
            lecture.students_left_early = left_early
            db.commit()

        return {
            "session_id": session_id,
            "total_tracked": total_detected,
            "total_present": present_count,
            "students_left_early": left_early,
            "download_url": f"/api/attendance/export?session_id={session_id}",
        }

    def export_to_csv(self, db: Session, session_id: str) -> Path:
        """Export session attendance report to CSV using Pandas."""
        rows = self.evaluate_attendance(db, session_id)
        df = pd.DataFrame(
            rows
            or [
                {
                    "track_id": 0,
                    "student_id": "N/A",
                    "full_name": "No Attendance Data",
                    "dwell_seconds": 0,
                    "total_minutes_observed": 0.0,
                    "presence_status": "Absent",
                }
            ]
        )
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS_DIR / f"attendance_{session_id}.csv"
        df.to_csv(out_path, index=False)
        return out_path


attendance_manager = AttendanceManager()
