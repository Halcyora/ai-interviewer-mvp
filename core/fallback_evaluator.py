"""
Fallback evaluator when Bedrock models are unavailable.
Uses simple keyword matching instead of LLM-based evaluation.
"""
import json
from typing import List


def extract_keywords(text: str, max_words: int = 10) -> List[str]:
    """Extract important keywords from text (words > 3 chars)."""
    words = text.lower().split()
    keywords = [w.strip('.,!?;:') for w in words if len(w) > 3]
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
    context_keywords = set(extract_keywords(context_chunks, max_words=15))
    answer_keywords = set(extract_keywords(candidate_answer, max_words=20))
    question_keywords = set(extract_keywords(question_text, max_words=10))
    
    # Calculate coverage: how many context keywords appear in answer
    covered = answer_keywords & context_keywords
    coverage_ratio = len(covered) / max(len(context_keywords), 1)
    
    # Adjust score based on coverage
    # 0.7+ coverage = good (0.8), 0.4-0.7 = partial (0.6), <0.4 = poor (0.4)
    if coverage_ratio >= 0.7:
        score = 0.8
        reasoning = "Answer covers key concepts well"
    elif coverage_ratio >= 0.4:
        score = 0.6
        reasoning = "Answer addresses some key concepts but lacks depth"
    else:
        score = 0.4
        reasoning = "Answer does not sufficiently cover key concepts"
    
    return {
        "score": round(score, 2),
        "reasoning": reasoning,
        "key_points_covered": list(covered)[:5],
        "missing_points": list(context_keywords - covered)[:5],
    }
