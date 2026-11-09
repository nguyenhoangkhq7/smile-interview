"""Retired interview endpoints. All new interviews use the evidence workflow."""
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/v1/interview", tags=["Retired interview API"])
RETIRED_MESSAGE = "Luồng phỏng vấn cũ đã ngừng hỗ trợ. Hãy tạo lượt phỏng vấn mới bằng V2."


@router.post("/start", deprecated=True)
@router.post("/respond", deprecated=True)
@router.get("/report/{session_id}", deprecated=True)
def retired_interview(session_id: str | None = None):
    raise HTTPException(status_code=410, detail=RETIRED_MESSAGE)
