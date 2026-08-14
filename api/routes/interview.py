import json
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.crud import create_session
from models.interview import AnswerIn, EvaluationOut
from models.session import SessionCreate
from core.orchestrator import init_session, get_next_question, submit_answer, load_session
from rag.vectorstore import get_collection

router = APIRouter()

# Define available companies and roles
COMPANIES = ["google", "amazon", "meta", "apple", "netflix"]
ROLES = [
    "software_engineer",
    "senior_software_engineer",
    "staff_engineer",
    "engineering_manager",
    "product_manager"
]


@router.get("/companies")
async def list_companies():
    """Returns available companies and their roles."""
    return {
        "companies": COMPANIES,
        "roles": ROLES,
        "total_combinations": len(COMPANIES) * len(ROLES)
    }


@router.get("/contexts")
async def list_contexts():
    """Returns context names that have a matching questions file."""
    questions_dir = Path("data/questions")
    contexts = [
        f.stem.replace("_questions", "")
        for f in sorted(questions_dir.glob("*_questions.json"))
    ]
    return {"contexts": contexts}


@router.post("/start")
async def start_interview(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    # Derive context_name from company and role
    if not body.context_name:
        body.context_name = f"{body.company}_{body.role}"
    
    q_path = Path("data/questions") / f"{body.context_name}_questions.json"
    if not q_path.exists():
        raise HTTPException(404, f"Question file not found: {q_path}. Expected: {body.company}/{body.role}")
    
    # Validate context is ingested in ChromaDB (C4: avoid empty retrieval)
    collection = get_collection()
    if collection.count() == 0:
        raise HTTPException(400, f"Context '{body.context_name}' not ingested. Run: python -m scripts.ingest --context data/context/{body.context_name}.txt")
    
    questions_data = json.loads(q_path.read_text(encoding="utf-8"))
    session_id = str(uuid.uuid4())
    
    # Count total questions across all difficulties
    total_questions = len(questions_data.get("questions", []))
    
    await create_session(db, session_id, body.context_name, total_questions)
    init_session(session_id, questions_data.get("questions", []), company=body.company, role=body.role)
    first_q = await get_next_question(session_id, db)
    return {
        "session_id": session_id,
        "first_question": first_q,
        "company": body.company,
        "role": body.role,
        "total_questions": total_questions
    }


@router.post("/answer", response_model=EvaluationOut)
async def answer_question(body: AnswerIn, db: AsyncSession = Depends(get_db)):
    s = load_session(body.session_id)
    if not s:
        raise HTTPException(404, "Session not found or expired")
    if s.state != "AWAITING_ANSWER":
        raise HTTPException(400, f"Not awaiting answer (current state: {s.state})")
    
    # Validate turn_index matches server state (prevent client/server drift)
    if body.turn_index != s.global_turn_index:
        raise HTTPException(400, f"Turn index mismatch: expected {s.global_turn_index}, got {body.turn_index}. Page may be out of sync.")
    
    return await submit_answer(body.session_id, body.answer_text, body.answer_mode, db)


@router.get("/status/{session_id}")
async def get_status(session_id: str):
    s = load_session(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    topic = s.topics[s.current_topic_index] if s.current_topic_index < len(s.topics) else None
    return {
        "session_id": session_id,
        "state": s.state,
        "current_topic_index": s.current_topic_index,
        "total_topics": len(s.topics),
        "current_topic_label": topic.topic_label if topic else None,
        "global_turn_index": s.global_turn_index,
    }
