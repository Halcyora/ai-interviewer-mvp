import json
import uuid
import random
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.crud import create_session, update_session_state, log_state_transition
from models.interview import AnswerIn, EvaluationOut
from models.session import SessionCreate
from core.orchestrator import init_session, get_next_question, submit_answer, load_session, end_session
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
MAX_INTERVIEW_QUESTIONS = 10


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
    # Accept either explicit context_name (UI flow) or company+role (API flow)
    if body.context_name:
        questions_context = body.context_name
    elif body.company and body.role:
        questions_context = f"{body.company}_{body.role}"
    else:
        raise HTTPException(422, "Provide either context_name, or both company and role.")
    
    q_path = Path("data/questions") / f"{questions_context}_questions.json"
    if not q_path.exists():
        raise HTTPException(404, f"Question file not found: {q_path}")
    
    # Determine the source used in Chroma metadata for retrieval/filtering.
    source_name = body.company
    if not source_name:
        if questions_context in COMPANIES:
            source_name = questions_context
        else:
            company_prefix = next((c for c in COMPANIES if questions_context.startswith(f"{c}_")), None)
            source_name = company_prefix or questions_context

    # Validate context is ingested in ChromaDB
    collection = get_collection()
    results = collection.get(
        where={"source": {"$eq": source_name}},
        include=["documents"],
    )
    if not results.get("ids"):
        raise HTTPException(400, f"Context for '{source_name}' not ingested. Run: python -m scripts.ingest --context data/context/{source_name}.txt")
    
    questions_data = json.loads(q_path.read_text(encoding="utf-8"))
    session_id = str(uuid.uuid4())
    
    # Support both "questions" array (old format) and "topics" array (LLM-generated)
    questions_list = questions_data.get("questions", []) or questions_data.get("topics", [])

    # Optional difficulty filter from UI/API.
    if body.difficulty:
        questions_list = [q for q in questions_list if (q.get("difficulty") or "").lower() == body.difficulty]

    if not questions_list:
        raise HTTPException(400, "No questions available for the selected context/difficulty.")

    # Keep interview concise.
    random.shuffle(questions_list)
    questions_list = questions_list[:MAX_INTERVIEW_QUESTIONS]
    total_questions = len(questions_list)
    
    await create_session(db, session_id, questions_context, total_questions)
    init_session(
        session_id,
        questions_list,
        company=source_name,
        role=body.role,
        difficulty=body.difficulty,
        max_questions=MAX_INTERVIEW_QUESTIONS,
    )
    first_q = await get_next_question(session_id, db)
    return {
        "session_id": session_id,
        "first_question": first_q,
        "company": source_name,
        "role": body.role,
        "difficulty": body.difficulty,
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

    try:
        return await submit_answer(body.session_id, body.answer_text, body.answer_mode, db)
    except Exception as exc:
        # Keep the session usable after downstream failures (e.g., LLM provider errors).
        active = load_session(body.session_id)
        if active and active.state == "EVALUATING":
            active.state = "AWAITING_ANSWER"
        raise HTTPException(502, f"Answer evaluation failed: {exc}")


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
        "difficulty": s.difficulty,
    }


@router.post("/leave/{session_id}")
async def leave_interview(session_id: str, db: AsyncSession = Depends(get_db)):
    s = load_session(session_id)
    if not s:
        raise HTTPException(404, "Session not found or already closed")

    old_state = s.state
    end_session(session_id)

    await update_session_state(db, session_id, "COMPLETED")
    await log_state_transition(
        db,
        session_id,
        old_state,
        "COMPLETED",
        "CANDIDATE_LEFT",
        None,
        None,
    )

    return {
        "session_id": session_id,
        "status": "left",
    }
