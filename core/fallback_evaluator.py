"""
Fallback evaluator when Bedrock models are unavailable.
Uses simple keyword matching instead of LLM-based evaluation.
"""
import json
from typing import List


STOPWORDS = {
    "the", "a", "an", "and", "or", "to", "of", "in", "for", "on", "with", "at", "by",
    "from", "is", "are", "was", "were", "be", "been", "being", "it", "this", "that", "as",
    "how", "what", "why", "when", "where", "who", "which", "does", "do", "did", "can", "could",
    "would", "should", "into", "about", "their", "they", "them", "you", "your", "our", "we",
}


def extract_keywords(text: str, max_words: int = 10) -> List[str]:
    """Extract important keywords from text."""
    words = text.lower().split()
    keywords = [w.strip('.,!?;:()[]{}\"\'') for w in words if len(w) > 2 and w not in STOPWORDS]
    return list(dict.fromkeys(keywords))[:max_words]  # Deduplicate, limit


async def fallback_evaluate_answer(
    topic_label: str,
    question_text: str,
    context_chunks: str,
    candidate_answer: str,
) -> dict:
    """
    Simple keyword-based evaluation without AWS.
    Returns: {score, reasoning, key_points_covered, missing_points}
    """
    context_keywords = set(extract_keywords(context_chunks, max_words=40))
    answer_keywords = set(extract_keywords(candidate_answer, max_words=50))
    question_keywords = set(extract_keywords(question_text, max_words=20))

    # Core signals
    covered_context = answer_keywords & context_keywords
    covered_question = answer_keywords & question_keywords
    coverage_ratio = len(covered_context) / max(len(context_keywords), 1)
    question_fit_ratio = len(covered_question) / max(len(question_keywords), 1)

    # Weighted continuous score to avoid coarse ties:
    # - Question fit is primary
    # - Context grounding is secondary
    # - Small boost for multiple explicit covered points
    # Keep this lenient so clearly relevant answers are not under-scored.
    evidence_boost = min(len(covered_context) / 8.0, 1.0)
    raw = (
        0.10
        + (0.45 * question_fit_ratio)
        + (0.25 * coverage_ratio)
        + (0.20 * evidence_boost)
    )

    # Guardrails to preserve rubric semantics.
    if question_fit_ratio < 0.10 and coverage_ratio < 0.10:
        score = min(raw, 0.25)  # mostly irrelevant
    elif question_fit_ratio < 0.20 and coverage_ratio < 0.20:
        score = min(raw, 0.40)  # generic/weakly related
    elif question_fit_ratio >= 0.50 and len(covered_context) >= 1:
        score = max(raw, 0.70)  # context-good + question-specific floor
    elif question_fit_ratio >= 0.35 and len(covered_context) >= 1:
        score = max(raw, 0.60)  # moderate floor
    else:
        score = raw

    # Keep single-mechanism answers in moderate range unless question fit is strong.
    if len(covered_context) <= 1 and question_fit_ratio < 0.50:
        score = min(score, 0.65)

    score = max(0.0, min(1.0, round(score, 2)))

    if score >= 0.75:
        reasoning = "Answer is well-aligned to the question and strongly grounded in context"
    elif score >= 0.55:
        reasoning = "Answer is relevant and context-grounded but misses some important details"
    elif score >= 0.35:
        reasoning = "Answer is partially relevant but remains generic or lightly context-grounded"
    else:
        reasoning = "Answer is weakly aligned to the question and lacks key context points"
    
    return {
        "score": score,
        "reasoning": reasoning,
        "key_points_covered": list(covered_context)[:5],
        "missing_points": list(context_keywords - covered_context)[:5],
    }
