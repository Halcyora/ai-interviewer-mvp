import json
import logging
from config.settings import settings
from core.prompts import EVALUATOR
from core.llm_client import invoke_and_audit_llm
from core.fallback_evaluator import fallback_evaluate_answer

logger = logging.getLogger(__name__)


async def evaluate_answer(
    session_id: str,
    turn_id: int,
    topic_label: str,
    question_text: str,
    context_chunks: str,
    candidate_answer: str,
    prev_entry_hash: str,
    db,
) -> tuple:
    """
    Returns ({score, reasoning, key_points_covered, missing_points}, {input_tokens, output_tokens}).
    Key points derived from RAG context chunks — no pre-defined expected_key_points.
    Writes audit row (C3). Uses Haiku (C1, C2).
    Falls back to keyword-based evaluation if Bedrock is unavailable.
    """
    try:
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
            model_id=settings.bedrock_nova_lite_model_id,
            temperature=0.0,
            max_tokens=256,
            rendered_prompt=rendered,
            prompt=rendered,
        )
        try:
            parsed = json.loads(response_text)
            return parsed, {"input_tokens": meta.get("input_tokens", 0), "output_tokens": meta.get("output_tokens", 0)}
        except json.JSONDecodeError:
            logger.warning("Evaluator returned non-JSON response; using fallback evaluator")
            result = await fallback_evaluate_answer(
                topic_label=topic_label,
                question_text=question_text,
                context_chunks=context_chunks,
                candidate_answer=candidate_answer,
            )
            return result, {"input_tokens": meta.get("input_tokens", 0), "output_tokens": meta.get("output_tokens", 0)}
    except Exception as e:
        # If Bedrock or parsing fails, use fallback evaluator to keep interview flow stable.
        error_msg = str(e)
        logger.error(f"Evaluation provider failed! Exception: {type(e).__name__}: {error_msg}")
        logger.warning(f"Using fallback evaluator instead")
        result = await fallback_evaluate_answer(
            topic_label=topic_label,
            question_text=question_text,
            context_chunks=context_chunks,
            candidate_answer=candidate_answer,
        )
        return result, {"input_tokens": 0, "output_tokens": 0}
