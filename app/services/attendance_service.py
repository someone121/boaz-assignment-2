"""Automated visual attendance service with Strategy-pattern PresencePolicy, YOLO/ByteTrack, and self check-in."""

from abc import ABC, abstractmethod
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
import secrets
import tempfile
from typing import Optional

from fastapi import HTTPException, status
import pandas as pd
from sqlalchemy.orm import Session

from app.config import REPORTS_DIR, settings
from app.models import (
    ActiveCheckInToken,
    AttendanceCheckIn,
    AttendanceRecord,
    LectureSession,
    Student,
    utcnow,
)

VIDEO_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


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
    """YOLOv8n + ByteTrack person tracker with video sampling and graceful mock fallback."""

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
            self._model = None
            self.mode = "mock_yolo_bytetrack"

    @staticmethod
    def is_video(filename: str) -> bool:
        """Return True when filename has a supported video extension."""
        return Path(filename or "").suffix.lower() in VIDEO_EXTENSIONS

    def _track_image(self, image) -> list[int]:
        """Run YOLO + ByteTrack on a single decoded OpenCV frame."""
        results = self._model.track(
            image,
            persist=True,
            tracker="bytetrack.yaml",
            classes=[0],
            verbose=False,
        )
        if results and results[0].boxes is not None and results[0].boxes.id is not None:
            return [int(tid) for tid in results[0].boxes.id.tolist()]
        return []

    def detect_tracks(self, frame_bytes: bytes, filename: str = "") -> list[int]:
        """Run YOLOv8n + ByteTrack on an image, or simulate tracks in mock mode."""
        self._lazy_load()
        if self._model is not None and self._cv2 is not None and self._np is not None:
            buf = self._np.frombuffer(frame_bytes, dtype=self._np.uint8)
            image = self._cv2.imdecode(buf, self._cv2.IMREAD_COLOR)
            if image is not None:
                self.mode = "yolov8n_bytetrack"
                return self._track_image(image)

        self.mode = "mock_yolo_bytetrack"
        seed = (len(frame_bytes) + len(filename)) % 5
        count = 3 + seed
        return list(range(1, count + 1))

    def detect_video_tracks(
        self,
        video_bytes: bytes,
        filename: str = "lecture.mp4",
        sample_every_seconds: int = settings.VIDEO_SAMPLE_INTERVAL_SECONDS,
    ) -> dict[int, int]:
        """Sample frames from a video with OpenCV and run YOLO + ByteTrack on each.

        Returns a mapping of ``{track_id: sampled_appearances}``. Falls back to
        the mock tracker only when YOLO/OpenCV cannot load.
        """
        self._lazy_load()
        if self._model is None or self._cv2 is None:
            self.mode = "mock_yolo_bytetrack"
            seed = (len(video_bytes) + len(filename)) % 5
            return {tid: 1 for tid in range(1, 3 + seed + 1)}

        suffix = Path(filename or "video.mp4").suffix or ".mp4"
        tmp_path: Optional[Path] = None
        track_counts: dict[int, int] = {}
        try:
            with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
                tmp.write(video_bytes)
                tmp_path = Path(tmp.name)

            cap = self._cv2.VideoCapture(str(tmp_path))
            if not cap.isOpened():
                self.mode = "mock_yolo_bytetrack"
                return {1: 1, 2: 1, 3: 1}

            fps = cap.get(self._cv2.CAP_PROP_FPS) or 25.0
            if fps <= 0:
                fps = 25.0
            step = max(1, int(round(fps * max(1, sample_every_seconds))))

            frame_idx = 0
            sampled = 0
            max_samples = 120
            while sampled < max_samples:
                ok, frame = cap.read()
                if not ok:
                    break
                if frame_idx % step == 0:
                    sampled += 1
                    for tid in self._track_image(frame):
                        track_counts[tid] = track_counts.get(tid, 0) + 1
                frame_idx += 1
            cap.release()
            self.mode = "yolo_video"
            return track_counts
        finally:
            if tmp_path is not None and tmp_path.exists():
                tmp_path.unlink(missing_ok=True)

    def count_photo_with_boxes(self, image_bytes: bytes, filename: str = "photo.jpg") -> dict:
        """Count people in a single class photo and draw bounding boxes."""
        self._lazy_load()
        if self._model is not None and self._cv2 is not None and self._np is not None:
            buf = self._np.frombuffer(image_bytes, dtype=self._np.uint8)
            image = self._cv2.imdecode(buf, self._cv2.IMREAD_COLOR)
            if image is not None:
                results = self._model(image, classes=[0], verbose=False)
                boxes: list[dict] = []
                annotated = image.copy()
                if results and results[0].boxes is not None:
                    for box in results[0].boxes:
                        xyxy = box.xyxy[0].tolist()
                        conf = float(box.conf[0]) if box.conf is not None else 0.0
                        x1, y1, x2, y2 = [int(v) for v in xyxy]
                        boxes.append({"x1": x1, "y1": y1, "x2": x2, "y2": y2, "confidence": round(conf, 3)})
                        self._cv2.rectangle(annotated, (x1, y1), (x2, y2), (82, 133, 192), 2)
                        self._cv2.putText(
                            annotated,
                            f"Person {conf:.2f}",
                            (x1, max(16, y1 - 6)),
                            self._cv2.FONT_HERSHEY_SIMPLEX,
                            0.5,
                            (82, 133, 192),
                            2,
                        )
                self._cv2.putText(
                    annotated,
                    f"Detected: {len(boxes)}",
                    (16, 36),
                    self._cv2.FONT_HERSHEY_SIMPLEX,
                    1.0,
                    (43, 46, 75),
                    3,
                )
                ok, encoded = self._cv2.imencode(".jpg", annotated)
                b64 = (
                    f"data:image/jpeg;base64,{base64.b64encode(encoded.tobytes()).decode('ascii')}"
                    if ok
                    else None
                )
                self.mode = "yolov8n_photo"
                return {
                    "count": len(boxes),
                    "boxes": boxes,
                    "annotated_image_base64": b64,
                    "detector_mode": self.mode,
                }

        seed = (len(image_bytes) + len(filename)) % 5
        count = 3 + seed
        boxes = [
            {"x1": 20 + i * 50, "y1": 30, "x2": 60 + i * 50, "y2": 140, "confidence": 0.9}
            for i in range(count)
        ]
        self.mode = "mock_yolo_bytetrack"
        return {
            "count": count,
            "boxes": boxes,
            "annotated_image_base64": None,
            "detector_mode": self.mode,
        }


class AttendanceManager:
    """Coordinates camera tracking, self check-in QR, dwell accumulation, and CSV/XLSX export."""

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
        """Process a classroom image or video upload, update dwell times, and persist records."""
        self.ensure_session(session_id)
        tracks = self.active_sessions[session_id]

        if self.tracker.is_video(filename):
            track_counts = self.tracker.detect_video_tracks(
                frame_bytes, filename=filename, sample_every_seconds=interval_seconds
            )
            detected_track_ids = list(track_counts.keys())
        else:
            detected_track_ids = self.tracker.detect_tracks(frame_bytes, filename)
            track_counts = {tid: 1 for tid in detected_track_ids}

        session_start = self.session_starts[session_id]
        max_samples = max(track_counts.values(), default=1)
        session_total_seconds = max(
            interval_seconds * max_samples,
            int((datetime.now(timezone.utc) - session_start).total_seconds()) + interval_seconds,
        )

        for track_id, appearances in track_counts.items():
            if track_id not in tracks:
                tracks[track_id] = TrackedPerson(track_id=track_id)
            tracks[track_id].update_presence(interval_seconds * appearances)

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

    def trigger_checkin(
        self,
        db: Session,
        session_id: str,
        lecturer_id: Optional[str] = None,
        ttl_seconds: int = 300,
    ) -> dict:
        """Issue a short-lived QR token for student self check-in."""
        lecture = db.get(LectureSession, session_id)
        if lecture is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found.")
        now = utcnow()
        token_value = f"att_{secrets.token_urlsafe(12)}"
        row = ActiveCheckInToken(
            token=token_value,
            session_id=session_id,
            lecturer_id=lecturer_id,
            created_at=now,
            expires_at=now + timedelta(seconds=ttl_seconds),
            is_active=True,
        )
        db.add(row)
        db.commit()
        return {
            "token": token_value,
            "session_id": session_id,
            "course_name": lecture.course_name,
            "qr_path": f"/checkin/{token_value}",
            "expires_at": row.expires_at.isoformat(),
            "ttl_seconds": ttl_seconds,
        }

    def get_checkin_info(self, db: Session, token: str) -> dict:
        """Validate an attendance self check-in token and return session metadata."""
        row = db.get(ActiveCheckInToken, token)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in token not found.")
        if not row.is_active or utcnow() > row.expires_at:
            raise HTTPException(
                status_code=status.HTTP_410_GONE,
                detail="The attendance check-in QR has expired.",
            )
        lecture = db.get(LectureSession, row.session_id)
        seconds_left = max(0, int((row.expires_at - utcnow()).total_seconds()))
        return {
            "token": row.token,
            "session_id": row.session_id,
            "course_name": lecture.course_name if lecture else "Class Session",
            "seconds_remaining": seconds_left,
        }

    def submit_checkin(
        self, db: Session, token: str, student_id: str, full_name: str
    ) -> dict:
        """Record a student's self check-in for the token's lecture session."""
        row = db.get(ActiveCheckInToken, token)
        if row is None:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Check-in token not found.")
        if not row.is_active or utcnow() > row.expires_at:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="The attendance check-in QR has expired.",
            )

        student = db.get(Student, student_id)
        if student is None:
            student = Student(student_id=student_id, full_name=full_name)
            db.add(student)
            db.flush()

        existing = (
            db.query(AttendanceCheckIn)
            .filter(
                AttendanceCheckIn.session_id == row.session_id,
                AttendanceCheckIn.student_id == student_id,
            )
            .first()
        )
        if existing is None:
            existing = AttendanceCheckIn(
                session_id=row.session_id,
                student_id=student_id,
                student_name=full_name,
                token=token,
                checked_in_at=utcnow(),
            )
            db.add(existing)
            db.commit()
            db.refresh(existing)

        return {
            "status": "checked_in",
            "session_id": row.session_id,
            "student_id": existing.student_id,
            "student_name": existing.student_name,
            "checked_in_at": existing.checked_in_at.isoformat(),
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
        """Merge camera tracks and self check-ins into unified attendance rows."""
        lecture = db.get(LectureSession, session_id)
        records = (
            db.query(AttendanceRecord)
            .filter(AttendanceRecord.session_id == session_id)
            .order_by(AttendanceRecord.track_id.asc())
            .all()
        )
        checkins = (
            db.query(AttendanceCheckIn)
            .filter(AttendanceCheckIn.session_id == session_id)
            .order_by(AttendanceCheckIn.checked_in_at.asc())
            .all()
        )
        checkins_by_student = {c.student_id: c for c in checkins}

        if lecture and lecture.end_time and lecture.start_time:
            total_seconds = max(1, int((lecture.end_time - lecture.start_time).total_seconds()))
        elif lecture and lecture.start_time:
            total_seconds = max(1, int((utcnow() - lecture.start_time).total_seconds()))
        else:
            total_seconds = max([r.dwell_seconds for r in records], default=1)

        report: list[dict] = []
        seen_students: set[str] = set()

        for rec in records:
            student = db.get(Student, rec.student_id) if rec.student_id else None
            checkin = checkins_by_student.get(rec.student_id) if rec.student_id else None
            if rec.student_id:
                seen_students.add(rec.student_id)

            camera_ok = self.policy.is_eligible(rec.dwell_seconds, total_seconds)
            rec.is_eligible = camera_ok or (checkin is not None)
            dwell_min = round(rec.dwell_seconds / 60, 2)
            display_name = student.full_name if student else (
                checkin.student_name if checkin else "Unassigned Student"
            )
            source = "both" if checkin is not None else "camera"
            report.append(
                {
                    "track_id": rec.track_id,
                    "student_id": rec.student_id or f"Track-{rec.track_id}",
                    "name": display_name,
                    "full_name": display_name,
                    "checked_in_at": checkin.checked_in_at.isoformat() if checkin else "",
                    "camera_dwell_minutes": dwell_min,
                    "dwell_seconds": rec.dwell_seconds,
                    "total_minutes_observed": dwell_min,
                    "presence_status": "Present" if rec.is_eligible else "Absent",
                    "source": source,
                }
            )

        for checkin in checkins:
            if checkin.student_id in seen_students:
                continue
            report.append(
                {
                    "track_id": 0,
                    "student_id": checkin.student_id,
                    "name": checkin.student_name,
                    "full_name": checkin.student_name,
                    "checked_in_at": checkin.checked_in_at.isoformat(),
                    "camera_dwell_minutes": 0.0,
                    "dwell_seconds": 0,
                    "total_minutes_observed": 0.0,
                    "presence_status": "Present",
                    "source": "self_checkin",
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
            "xlsx_download_url": f"/api/attendance/export-xlsx?session_id={session_id}",
        }

    def _build_export_dataframe(self, db: Session, session_id: str) -> pd.DataFrame:
        rows = self.evaluate_attendance(db, session_id)
        if not rows:
            rows = [
                {
                    "track_id": 0,
                    "student_id": "N/A",
                    "name": "No Attendance Data",
                    "full_name": "No Attendance Data",
                    "checked_in_at": "",
                    "camera_dwell_minutes": 0.0,
                    "dwell_seconds": 0,
                    "total_minutes_observed": 0.0,
                    "presence_status": "Absent",
                    "source": "none",
                }
            ]
        return pd.DataFrame(rows)

    def export_to_csv(self, db: Session, session_id: str) -> Path:
        """Export session attendance report to CSV using Pandas."""
        df = self._build_export_dataframe(db, session_id)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS_DIR / f"attendance_{session_id}.csv"
        df.to_csv(out_path, index=False)
        return out_path

    def export_to_xlsx(self, db: Session, session_id: str) -> Path:
        """Export session attendance report to an Excel (.xlsx) workbook."""
        df = self._build_export_dataframe(db, session_id)
        columns = [
            "student_id",
            "name",
            "checked_in_at",
            "camera_dwell_minutes",
            "presence_status",
            "source",
        ]
        df_xlsx = df[[c for c in columns if c in df.columns]]
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        out_path = REPORTS_DIR / f"attendance_{session_id}.xlsx"
        df_xlsx.to_excel(out_path, index=False, sheet_name="Attendance")
        return out_path


attendance_manager = AttendanceManager()
