"""Attendance tracking and CSV/Excel export endpoints."""

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
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
    """Ingest a classroom image/video frame, run mock YOLO tracking, and update dwell times."""
    frame_bytes = await file.read()
    return attendance_manager.process_frame(
        db=db,
        session_id=session_id,
        frame_bytes=frame_bytes,
        filename=file.filename or "frame.jpg",
        interval_seconds=interval_seconds,
    )


@router.get("/status/{session_id}")
def get_attendance_status(session_id: str, db: Session = Depends(get_db)) -> dict:
    """Return live tracked attendance rows for a session."""
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
