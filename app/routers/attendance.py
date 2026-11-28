"""Attendance tracking, self check-in QR, photo counting, and CSV/XLSX export endpoints."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas import CheckInSubmitRequest, CheckInTriggerRequest
from app.services.attendance_service import attendance_manager
from app.services.ws_manager import ws_manager

router = APIRouter(prefix="/api/attendance", tags=["Attendance"])


@router.post("/frame")
async def ingest_attendance_frame(
    session_id: str = Form(...),
    interval_seconds: int = Form(5),
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> dict:
    """Ingest a classroom image or video, run YOLO + ByteTrack, and update dwell times."""
    frame_bytes = await file.read()
    return attendance_manager.process_frame(
        db=db,
        session_id=session_id,
        frame_bytes=frame_bytes,
        filename=file.filename or "frame.jpg",
        interval_seconds=interval_seconds,
    )


@router.post("/count-photo")
async def count_people_in_photo(
    file: UploadFile = File(...),
) -> dict:
    """Count people in a single class photo and return bounding boxes + annotated image."""
    image_bytes = await file.read()
    return attendance_manager.tracker.count_photo_with_boxes(
        image_bytes, filename=file.filename or "photo.jpg"
    )


@router.post("/checkin/trigger")
def trigger_attendance_checkin(
    payload: CheckInTriggerRequest, db: Session = Depends(get_db)
) -> dict:
    """Create a short-lived attendance self check-in QR token."""
    return attendance_manager.trigger_checkin(
        db=db,
        session_id=payload.session_id,
        lecturer_id=payload.lecturer_id,
        ttl_seconds=payload.ttl_seconds,
    )


@router.get("/checkin/{token}")
def get_checkin_details(token: str, db: Session = Depends(get_db)) -> dict:
    """Validate an attendance check-in token and return session info."""
    return attendance_manager.get_checkin_info(db, token)


@router.post("/checkin/submit")
async def submit_attendance_checkin(
    payload: CheckInSubmitRequest, db: Session = Depends(get_db)
) -> dict:
    """Record a student's self check-in and notify connected dashboards."""
    result = attendance_manager.submit_checkin(
        db=db,
        token=payload.token,
        student_id=payload.student_id,
        full_name=payload.full_name,
    )
    await ws_manager.broadcast_event(
        result["session_id"],
        "ATTENDANCE_UPDATE",
        {
            "session_id": result["session_id"],
            "student_id": result["student_id"],
            "student_name": result["student_name"],
        },
    )
    return result


@router.get("/status/{session_id}")
def get_attendance_status(session_id: str, db: Session = Depends(get_db)) -> dict:
    """Return live tracked + self-checked-in attendance rows for a session."""
    rows = attendance_manager.evaluate_attendance(db, session_id)
    return {
        "session_id": session_id,
        "total_tracked": len(rows),
        "records": rows,
    }


@router.post("/stop")
async def stop_attendance_session(session_id: str, db: Session = Depends(get_db)) -> dict:
    """Finalize session attendance and broadcast ATTENDANCE_DONE over WebSocket."""
    summary = attendance_manager.stop_session(db, session_id)
    attendance_manager.export_to_csv(db, session_id)
    await ws_manager.broadcast_event(
        session_id,
        "ATTENDANCE_DONE",
        {
            "download_url": summary["download_url"],
            "xlsx_download_url": summary["xlsx_download_url"],
            "total_present": summary["total_present"],
        },
    )
    return summary


@router.get("/export")
def export_attendance_csv(session_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Download the compiled CSV attendance spreadsheet for a session."""
    csv_path = attendance_manager.export_to_csv(db, session_id)
    return FileResponse(
        path=str(csv_path),
        media_type="text/csv",
        filename=f"attendance_{session_id}.csv",
    )


@router.get("/export-xlsx")
def export_attendance_xlsx(session_id: str, db: Session = Depends(get_db)) -> FileResponse:
    """Download the compiled Excel (.xlsx) attendance spreadsheet for a session."""
    xlsx_path = attendance_manager.export_to_xlsx(db, session_id)
    return FileResponse(
        path=str(xlsx_path),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=f"attendance_{session_id}.xlsx",
    )
