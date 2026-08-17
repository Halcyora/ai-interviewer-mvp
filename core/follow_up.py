import json
from config.settings import settings
from core.prompts import FOLLOW_UP_GEN
from core.llm_client import invoke_and_audit_llm


def should_follow_up(confidence_score: float, stretch_count: int) -> str:
    """
    Returns 'FOLLOW_UP' or 'NEXT_TOPIC'.
    stretch_count is 1-based (1=seed Q answered, 2=first follow-up answered, ...).
    Max stretch = settings.max_stretch_count (default 3).
    """
    in_partial_range = (
        settings.follow_up_threshold_low
        <= confidence_score
        <= settings.follow_up_threshold_high
    )
    under_limit = stretch_count < settings.max_stretch_count
    if in_partial_range and under_limit:
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
) -> str:
    """Returns follow-up question text. Uses Haiku (C1, C2). Writes audit row (C3)."""
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
    return response_text.strip()
