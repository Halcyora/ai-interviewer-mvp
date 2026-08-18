from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.models import Report, InterviewSession
from db.crud import save_report, deserialize_json_field
from core.orchestrator import load_session
from core.reporter import generate_report
from models.report import ReportOut

router = APIRouter()


def _to_report_out(row: Report) -> dict:
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


@router.post("/generate/{session_id}", response_model=ReportOut)
async def generate(session_id: str, db: AsyncSession = Depends(get_db)):
    existing_result = await db.execute(
        select(Report).where(Report.session_id == session_id)
    )
    existing = existing_result.scalar_one_or_none()
    if existing:
        return _to_report_out(existing)

    s = load_session(session_id)
    orchestrator_state = None
    if s and s.state == "COMPLETED":
        orchestrator_state = s
    else:
        session_result = await db.execute(
            select(InterviewSession).where(InterviewSession.id == session_id)
        )
        session_row = session_result.scalar_one_or_none()
        if not session_row:
            raise HTTPException(404, "Session not found")
        if session_row.state != "COMPLETED":
            raise HTTPException(400, "Interview must be in COMPLETED state")

    report = await generate_report(session_id, orchestrator_state, db)
    saved = await save_report(db, report)
    report["created_at"] = saved.created_at
    return report


@router.get("/{session_id}", response_model=ReportOut)
async def get_report(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Report).where(Report.session_id == session_id)
    )
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Report not found")
    return _to_report_out(row)
