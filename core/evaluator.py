import json
from config.settings import settings
from core.prompts import EVALUATOR
from core.llm_client import invoke_and_audit_llm


async def evaluate_answer(
    session_id: str,
    turn_id: int,
    topic_label: str,
    question_text: str,
    context_chunks: str,
    candidate_answer: str,
    prev_entry_hash: str,
    db,
) -> dict:
    """
    Returns {score, reasoning, key_points_covered, missing_points}.
    Key points derived from RAG context chunks — no pre-defined expected_key_points.
    Writes audit row (C3). Uses Haiku (C1, C2).
    """
    rendered = EVALUATOR.format(
        topic_label=topic_label,
        question_text=question_text,
        context_chunks=context_chunks,
        candidate_answer=candidate_answer,
    )
    response_text, meta = await invoke_and_audit_llm(
        db=db,
        session_id=session_id,
        turn_id=turn_id,
        template_id="EVALUATOR",
        model_id=settings.bedrock_claude_haiku_model_id,
        temperature=0.0,
        max_tokens=256,
        rendered_prompt=rendered,
        prompt=rendered,
    )
    return json.loads(response_text)
