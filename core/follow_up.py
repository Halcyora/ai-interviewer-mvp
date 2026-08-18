import json
import logging
from config.settings import settings
from core.prompts import FOLLOW_UP_GEN
from core.llm_client import invoke_and_audit_llm
from core.fallback_follow_up import fallback_generate_follow_up

logger = logging.getLogger(__name__)


def should_follow_up(confidence_score: float, stretch_count: int) -> str:
    """
    Determines whether to ask a follow-up or move to the next topic.
    
    Scoring logic (lenient but fair):
    - score < 0.3: Completely incorrect → NEXT_TOPIC (no follow-up)
    - 0.3 <= score <= 0.7: Partial/good understanding → FOLLOW_UP (if under limit)
    - score > 0.7: Strong understanding → NEXT_TOPIC (no follow-up needed)
    
    Args:
        confidence_score: Float between 0.0 and 1.0
        stretch_count: 1-based counter (1=seed Q, 2=1st follow-up, 3=2nd follow-up)
    
    Returns:
        'FOLLOW_UP' if score in 0.3-0.7 range and not exceeded max follow-ups
        'NEXT_TOPIC' otherwise
    """
    # Score < 0.3: completely incorrect/off-topic, move to next topic
    if confidence_score < 0.3:
        return "NEXT_TOPIC"
    
    # Score > 0.7: strong understanding, move to next topic
    if confidence_score > 0.7:
        return "NEXT_TOPIC"
    
    # Score 0.3-0.7: partial/good understanding, ask follow-up if within limit
    # stretch_count < 3 means we can do at most 2 follow-ups (on top of seed question)
    if stretch_count < settings.max_stretch_count:
        return "FOLLOW_UP"
    
    return "NEXT_TOPIC"


async def generate_follow_up(
    session_id: str,
    turn_id: int,
    topic_label: str,
    original_question: str,
    candidate_answer: str,
    confidence_score: float,
    missing_points: list,
    context_chunks: str,
    prev_entry_hash: str,
    db,
) -> tuple:
    """Returns (follow_up_question_text, {input_tokens, output_tokens}). Uses Haiku (C1, C2). Writes audit row (C3).
    Falls back to template-based generation if Bedrock is unavailable.
    """
    try:
        rendered = FOLLOW_UP_GEN.format(
            topic_label=topic_label,
            original_question=original_question,
            candidate_answer=candidate_answer,
            confidence_score=confidence_score,
            missing_points=json.dumps(missing_points),
            context_chunks=context_chunks,
        )
        response_text, meta = await invoke_and_audit_llm(
            db=db,
            session_id=session_id,
            turn_id=turn_id,
            template_id="FOLLOW_UP_GEN",
            model_id=settings.bedrock_nova_lite_model_id,
            temperature=0.7,
            max_tokens=200,
            rendered_prompt=rendered,
            prompt=rendered,
        )
        return response_text.strip(), {"input_tokens": meta.get("input_tokens", 0), "output_tokens": meta.get("output_tokens", 0)}
    except Exception as e:
        # If Bedrock fails, use fallback generator
        error_msg = str(e)
        if "AccessDeniedException" in error_msg or "INVALID_PAYMENT" in error_msg:
            logger.warning(f"Bedrock follow-up generation failed ({error_msg[:100]}), using fallback generator")
            result = await fallback_generate_follow_up(
                topic_label=topic_label,
                original_question=original_question,
                candidate_answer=candidate_answer,
                confidence_score=confidence_score,
                missing_points=missing_points,
                context_chunks=context_chunks,
            )
            return result, {"input_tokens": 0, "output_tokens": 0}
        # Re-raise other errors
        raise
