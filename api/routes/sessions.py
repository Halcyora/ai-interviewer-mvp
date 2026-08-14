from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.models import InterviewSession
from db.crud import get_by_id
from models.session import SessionOut

router = APIRouter()


@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    row = await get_by_id(db, InterviewSession, session_id)
    if not row:
        raise HTTPException(404, "Session not found")
    return {
        "id": row.id, "state": row.state, "context_name": row.context_name,
        "total_topics": row.total_topics, "completed_topics": row.completed_topics,
        "overall_score": row.overall_score, "overall_grade": row.overall_grade,
        "estimated_cost_usd": row.estimated_cost_usd,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }
