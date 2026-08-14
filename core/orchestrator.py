"""
One InterviewState per active session, held in the module-level _sessions dict.

State machine transitions:
  STARTED        -> AWAITING_ANSWER  (get_next_question called)
  AWAITING_ANSWER -> EVALUATING      (submit_answer called)
  EVALUATING     -> FOLLOW_UP -> AWAITING_ANSWER  (partial score, stretch < limit)
  EVALUATING     -> NEXT_TOPIC -> AWAITING_ANSWER  (high/low score or stretch limit)
  NEXT_TOPIC     -> COMPLETED        (no more topics)
"""
from dataclasses import dataclass, field
from typing import List, Optional
import random
from core.evaluator import evaluate_answer
from core.follow_up import should_follow_up, generate_follow_up
from core.scorer import compute_topic_score, score_to_grade
from rag.retriever import retrieve
from db.crud import (
    create_turn, update_turn_answer, upsert_topic_score,
    log_rag_retrieval, log_state_transition,
)


@dataclass
class TopicState:
    topic_id: str
    text: str  # question text
    difficulty: Optional[str] = None  # beginner, intermediate, advanced
    topic: Optional[str] = None  # topic area
    stretch_count: int = 0           # 1-based after first Q asked
    scores: List[float] = field(default_factory=list)
    current_question: str = ""
    context_chunks: str = ""
    current_turn_db_id: int = 0      # Turn.id from DB
    
    # Legacy support
    topic_label: Optional[str] = None
    seed_question: Optional[str] = None


@dataclass
class InterviewState:
    session_id: str
    state: str
    topics: List[TopicState]
    current_topic_index: int = 0
    global_turn_index: int = 0       # 0-based, increments after each answer submitted
    haiku_input_tokens: int = 0
    haiku_output_tokens: int = 0
    sonnet_input_tokens: int = 0
    sonnet_output_tokens: int = 0
    company: Optional[str] = None
    role: Optional[str] = None


# Module-level session registry — one entry per active session
_sessions: dict[str, InterviewState] = {}


def load_session(session_id: str) -> Optional[InterviewState]:
    return _sessions.get(session_id)


def init_session(session_id: str, questions_json: List[dict], company: Optional[str] = None, role: Optional[str] = None) -> InterviewState:
    """Initialize session with questions. Randomly select first question if many available."""
    topics = []
    for q in questions_json:
        topic = TopicState(
            topic_id=q.get("id", ""),
            text=q.get("text", q.get("seed_question", "")),
            difficulty=q.get("difficulty"),
            topic=q.get("topic"),
            topic_label=q.get("topic_label"),  # Legacy support
            seed_question=q.get("seed_question"),  # Legacy support
        )
        topics.append(topic)
    
    # Randomly shuffle to randomize question order (including first question)
    random.shuffle(topics)
    
    state = InterviewState(
        session_id=session_id,
        state="STARTED",
        topics=topics,
        company=company,
        role=role
    )
    _sessions[session_id] = state
    return state


async def get_next_question(session_id: str, db) -> dict:
    """RAG retrieval + serve question. Advances state to AWAITING_ANSWER."""
    s = _sessions[session_id]
    topic = s.topics[s.current_topic_index]

    # Use text field (new structure) or seed_question (legacy)
    question_text = topic.text or topic.seed_question or ""

    # Retrieve top-k chunks; HNSW index already warmed at startup (C1)
    results = retrieve(question_text)
    topic.context_chunks = "\n\n---\n\n".join(r[1] for r in results)
    await log_rag_retrieval(
        db, s.session_id, s.global_turn_index, topic.topic_id,
        question_text, [r[0] for r in results], [r[2] for r in results],
    )

    # Serve question directly — zero LLM call (C1 + C2)
    topic.current_question = question_text
    topic.stretch_count = 1

    turn_db_id = await create_turn(
        db, s.session_id, s.global_turn_index,
        topic.topic_id, 0, topic.current_question, "SEED",
    )
    topic.current_turn_db_id = turn_db_id

    old_state = s.state
    s.state = "AWAITING_ANSWER"
    await log_state_transition(
        db, s.session_id, old_state, "AWAITING_ANSWER", "QUESTION_PRESENTED", None, None
    )

    return {
        "session_id": s.session_id,
        "turn_index": s.global_turn_index,
        "topic_id": topic.topic_id,
        "stretch_index": 0,
        "question_text": topic.current_question,
        "question_type": "SEED",
        "difficulty": topic.difficulty,
        "topic": topic.topic,
        "total_topics": len(s.topics),
    }


async def submit_answer(session_id: str, answer_text: str, answer_mode: str, db) -> dict:
    """Evaluate answer -> decide follow-up or next topic -> return next action + question."""
    s = _sessions[session_id]
    topic = s.topics[s.current_topic_index]

    s.state = "EVALUATING"
    await log_state_transition(
        db, s.session_id, "AWAITING_ANSWER", "EVALUATING", "ANSWER_SUBMITTED", None, None
    )

    # Use topic_label (legacy) or topic field (new structure)
    label = topic.topic_label or topic.topic or topic.difficulty or "Unknown"

    eval_result = await evaluate_answer(
        session_id=s.session_id, turn_id=topic.current_turn_db_id,
        topic_label=label, question_text=topic.current_question,
        context_chunks=topic.context_chunks, candidate_answer=answer_text,
        prev_entry_hash="", db=db,
    )

    score: float = eval_result["score"]
    topic.scores.append(score)
    await update_turn_answer(db, topic.current_turn_db_id, answer_text, answer_mode, eval_result)
    s.global_turn_index += 1

    next_action = should_follow_up(score, topic.stretch_count)

    if next_action == "FOLLOW_UP":
        s.state = "FOLLOW_UP"
        follow_up_text = await generate_follow_up(
            session_id=s.session_id, turn_id=s.global_turn_index,
            topic_label=topic.topic_label, original_question=topic.current_question,
            candidate_answer=answer_text, confidence_score=score,
            missing_points=eval_result["missing_points"],
            context_chunks=topic.context_chunks,
            prev_entry_hash="", db=db,
        )
        topic.current_question = follow_up_text
        topic.stretch_count += 1

        turn_db_id = await create_turn(
            db, s.session_id, s.global_turn_index, topic.topic_id,
            topic.stretch_count - 1, follow_up_text, "FOLLOW_UP",
        )
        topic.current_turn_db_id = turn_db_id
        s.state = "AWAITING_ANSWER"
        await log_state_transition(
            db, s.session_id, "FOLLOW_UP", "AWAITING_ANSWER",
            "FOLLOW_UP_GENERATED", score, topic.stretch_count,
        )
        return {
            "confidence_score": score,
            "reasoning": eval_result["reasoning"],
            "key_points_covered": eval_result["key_points_covered"],
            "missing_points": eval_result["missing_points"],
            "next_action": "FOLLOW_UP",
            "next_question": {
                "session_id": s.session_id,
                "turn_index": s.global_turn_index,
                "topic_id": topic.topic_id,
                "stretch_index": topic.stretch_count - 1,
                "question_text": follow_up_text,
                "question_type": "FOLLOW_UP",
                "total_topics": len(s.topics),
            },
        }
    else:
        # Finalise topic score and advance
        topic_avg = compute_topic_score(topic.scores)
        grade = score_to_grade(topic_avg)
        await upsert_topic_score(
            db, s.session_id, topic.topic_id, topic.topic_label,
            len(topic.scores), topic_avg, grade,
        )
        s.current_topic_index += 1

        if s.current_topic_index >= len(s.topics):
            s.state = "COMPLETED"
            await log_state_transition(
                db, s.session_id, "NEXT_TOPIC", "COMPLETED",
                "ALL_TOPICS_DONE", score, topic.stretch_count,
            )
            return {
                "confidence_score": score,
                "reasoning": eval_result["reasoning"],
                "key_points_covered": eval_result["key_points_covered"],
                "missing_points": eval_result["missing_points"],
                "next_action": "COMPLETED",
                "next_question": None,
            }
        else:
            s.state = "NEXT_TOPIC"
            await log_state_transition(
                db, s.session_id, "EVALUATING", "NEXT_TOPIC",
                "TOPIC_FINISHED", score, topic.stretch_count,
            )
            next_q = await get_next_question(session_id, db)
            return {
                "confidence_score": score,
                "reasoning": eval_result["reasoning"],
                "key_points_covered": eval_result["key_points_covered"],
                "missing_points": eval_result["missing_points"],
                "next_action": "NEXT_TOPIC",
                "next_question": next_q,
            }
