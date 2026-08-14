import hashlib
import json
from typing import Optional, Type, TypeVar
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from sqlalchemy.orm import DeclarativeBase
from db.models import (
    InterviewSession, Turn, TopicScore, Report,
    LLMAuditLog, RAGAuditLog, StateTransitionLog,
)

T = TypeVar("T", bound=DeclarativeBase)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _audit_hash(session_id, turn_id, timestamp, prompt_hash, response_text, prev_hash) -> str:
    raw = f"{session_id}|{turn_id}|{timestamp}|{prompt_hash}|{response_text}|{prev_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()


# ── Session ───────────────────────────────────────────────────────────────────

async def create_session(
    db: AsyncSession, session_id: str, context_name: str, total_topics: int
) -> InterviewSession:
    now = _now()
    row = InterviewSession(
        id=session_id, created_at=now, updated_at=now,
        state="STARTED", context_name=context_name, total_topics=total_topics,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


async def update_session_state(db: AsyncSession, session_id: str, state: str, **kwargs):
    result = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    row = result.scalar_one()
    row.state = state
    row.updated_at = _now()
    for k, v in kwargs.items():
        setattr(row, k, v)
    await db.commit()


# ── Turn ──────────────────────────────────────────────────────────────────────

async def create_turn(
    db: AsyncSession, session_id: str, turn_index: int, topic_id: str,
    stretch_index: int, question_text: str, question_type: str,
) -> int:
    row = Turn(
        session_id=session_id, turn_index=turn_index, topic_id=topic_id,
        stretch_index=stretch_index, question_text=question_text,
        question_type=question_type, created_at=_now(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row.id


async def update_turn_answer(
    db: AsyncSession, turn_id: int, answer_text: str, answer_mode: str, eval_result: dict
):
    result = await db.execute(select(Turn).where(Turn.id == turn_id))
    row = result.scalar_one()
    row.answer_text = answer_text
    row.answer_mode = answer_mode
    row.confidence_score = eval_result["score"]
    row.reasoning = eval_result["reasoning"]
    row.key_points_covered = serialize_json_field(eval_result["key_points_covered"])
    row.missing_points = serialize_json_field(eval_result["missing_points"])
    await db.commit()


async def get_all_turns(db: AsyncSession, session_id: str) -> list:
    result = await db.execute(
        select(Turn).where(Turn.session_id == session_id).order_by(Turn.turn_index)
    )
    return result.scalars().all()


# ── Topic Score ───────────────────────────────────────────────────────────────

async def upsert_topic_score(
    db: AsyncSession, session_id: str, topic_id: str, topic_label: str,
    num_q: int, avg_score: float, grade: str,
):
    row = TopicScore(
        session_id=session_id, topic_id=topic_id, topic_label=topic_label,
        num_questions=num_q, avg_score=avg_score, grade=grade,
    )
    db.add(row)
    await db.commit()


async def get_topic_scores(db: AsyncSession, session_id: str) -> list:
    result = await db.execute(select(TopicScore).where(TopicScore.session_id == session_id))
    return result.scalars().all()


# ── Report ────────────────────────────────────────────────────────────────────

async def save_report(db: AsyncSession, report: dict) -> Report:
    row = Report(
        session_id=report["session_id"],
        created_at=_now(),
        overall_score=report["overall_score"],
        overall_grade=report["overall_grade"],
        strengths=serialize_json_field(report["strengths"]),
        gaps=serialize_json_field(report["gaps"]),
        narrative=report["narrative"],
        topic_breakdown=serialize_json_field(report["topic_breakdown"]),
        total_cost_usd=report["total_cost_usd"],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row


# ── Audit (append-only) ───────────────────────────────────────────────────────

async def append_llm_audit(
    db: AsyncSession, session_id: str, turn_id: int, template_id: str,
    model_id: str, temperature: float, max_tokens: int, rendered_prompt: str,
    response_text: str, input_tokens: int, output_tokens: int,
    latency_ms: int, prev_entry_hash: str,
) -> str:
    timestamp = _now()
    prompt_hash = hashlib.sha256(rendered_prompt.encode()).hexdigest()
    entry_hash = _audit_hash(
        session_id, turn_id, timestamp, prompt_hash, response_text, prev_entry_hash
    )
    row = LLMAuditLog(
        session_id=session_id, turn_id=turn_id, timestamp=timestamp,
        template_id=template_id, model_id=model_id, temperature=temperature,
        max_tokens=max_tokens, prompt_hash=prompt_hash, rendered_prompt=rendered_prompt,
        response_text=response_text, input_tokens=input_tokens, output_tokens=output_tokens,
        latency_ms=latency_ms, prev_entry_hash=prev_entry_hash, entry_hash=entry_hash,
    )
    db.add(row)
    await db.commit()
    return entry_hash


async def get_last_audit_hash(db: AsyncSession, session_id: str) -> str:
    result = await db.execute(
        select(LLMAuditLog.entry_hash)
        .where(LLMAuditLog.session_id == session_id)
        .order_by(LLMAuditLog.id.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row else "GENESIS"


async def log_rag_retrieval(
    db: AsyncSession, session_id: str, turn_id: int, topic_id: str,
    query_text: str, chunk_ids: list, scores: list,
):
    row = RAGAuditLog(
        session_id=session_id, turn_id=turn_id, timestamp=_now(),
        topic_id=topic_id, query_text=query_text,
        retrieved_chunk_ids=serialize_json_field(chunk_ids),
        retrieved_scores=serialize_json_field(scores),
    )
    db.add(row)
    await db.commit()


async def log_state_transition(
    db: AsyncSession, session_id: str, old_state: str, new_state: str,
    reason: str, confidence_score, stretch_count,
):
    row = StateTransitionLog(
        session_id=session_id, timestamp=_now(),
        old_state=old_state, new_state=new_state, reason=reason,
        confidence_score=confidence_score, stretch_count=stretch_count,
    )
    db.add(row)
    await db.commit()


# ── Generic Helpers ───────────────────────────────────────────────────────────

async def get_by_id(
    db: AsyncSession, model_class: Type[T], id_value: str, not_found_msg: str = "Resource not found"
) -> Optional[T]:
    """
    Generic helper to fetch a single resource by ID.
    Returns None if not found (caller should raise HTTPException if needed).
    """
    result = await db.execute(select(model_class).where(model_class.id == id_value))
    return result.scalar_one_or_none()


def serialize_json_field(data) -> str:
    """Serialize data to JSON string for database storage."""
    return json.dumps(data)


def deserialize_json_field(data: Optional[str]):
    """Deserialize JSON string from database. Returns None if data is None."""
    return json.loads(data) if data else None
