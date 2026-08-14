import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.models import Report
from db.crud import save_report, get_by_id, deserialize_json_field
from core.orchestrator import load_session
from core.reporter import generate_report
from models.report import ReportOut

router = APIRouter()


@router.post("/generate/{session_id}", response_model=ReportOut)
async def generate(session_id: str, db: AsyncSession = Depends(get_db)):
    s = load_session(session_id)
    if not s or s.state != "COMPLETED":
        raise HTTPException(400, "Interview must be in COMPLETED state")
    report = await generate_report(session_id, s, db)
    saved = await save_report(db, report)
    report["created_at"] = saved.created_at
    return report


@router.get("/{session_id}", response_model=ReportOut)
async def get_report(session_id: str, db: AsyncSession = Depends(get_db)):
    row = await get_by_id(db, Report, session_id)
    if not row:
        raise HTTPException(404, "Report not found")
    return {
        "session_id": row.session_id,
        "overall_score": row.overall_score,
        "overall_grade": row.overall_grade,
        "strengths": deserialize_json_field(row.strengths),
        "gaps": deserialize_json_field(row.gaps),
        "narrative": row.narrative,
        "topic_breakdown": deserialize_json_field(row.topic_breakdown),
        "total_cost_usd": row.total_cost_usd,
        "created_at": row.created_at,
    }
