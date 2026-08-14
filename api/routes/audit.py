from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from db.database import get_db
from db.models import LLMAuditLog, RAGAuditLog, StateTransitionLog
from models.audit import AuditTrailOut

router = APIRouter()


@router.get("/{session_id}", response_model=AuditTrailOut)
async def get_audit_trail(session_id: str, db: AsyncSession = Depends(get_db)):
    llm_rows = (
        await db.execute(
            select(LLMAuditLog)
            .where(LLMAuditLog.session_id == session_id)
            .order_by(LLMAuditLog.id)
        )
    ).scalars().all()
    rag_count = (
        await db.execute(
            select(func.count()).where(RAGAuditLog.session_id == session_id)
        )
    ).scalar()
    st_count = (
        await db.execute(
            select(func.count()).where(StateTransitionLog.session_id == session_id)
        )
    ).scalar()
    return {
        "session_id": session_id,
        "total_llm_calls": len(llm_rows),
        "total_rag_retrievals": rag_count,
        "total_state_transitions": st_count,
        "llm_entries": [
            {
                "id": r.id, "session_id": r.session_id, "turn_id": r.turn_id,
                "timestamp": r.timestamp, "template_id": r.template_id,
                "model_id": r.model_id, "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens, "latency_ms": r.latency_ms,
                "entry_hash": r.entry_hash,
            }
            for r in llm_rows
        ],
    }
