from typing import List, Dict, Any

# Descending threshold order — first match wins
_GRADE_MAP = [(0.8, "A"), (0.6, "B"), (0.4, "C"), (0.2, "D"), (0.0, "F")]


def score_to_grade(score: float) -> str:
    for threshold, grade in _GRADE_MAP:
        if score >= threshold:
            return grade
    return "F"


def compute_topic_score(scores: List[float]) -> float:
    return round(sum(scores) / len(scores), 4) if scores else 0.0


def compute_overall_score(topic_scores: List[float]) -> float:
    return round(sum(topic_scores) / len(topic_scores), 4) if topic_scores else 0.0


def compute_cost_usd(
    haiku_input_tokens: int,
    haiku_output_tokens: int,
    sonnet_input_tokens: int,
    sonnet_output_tokens: int,
) -> float:
    haiku = (haiku_input_tokens / 1000 * 0.001) + (haiku_output_tokens / 1000 * 0.005)
    sonnet = (sonnet_input_tokens / 1000 * 0.015) + (sonnet_output_tokens / 1000 * 0.075)
    return round(haiku + sonnet, 6)


def compute_session_scores(topic_score_rows: List[Any]) -> Dict[str, Any]:
    """
    Compute all scores for a session in one place.
    
    Args:
        topic_score_rows: List of TopicScore database rows with avg_score
        
    Returns:
        Dict with {overall_score, overall_grade, topic_scores}
    """
    topic_scores = [r.avg_score for r in topic_score_rows]
    overall_score = compute_overall_score(topic_scores)
    overall_grade = score_to_grade(overall_score)
    
    return {
        "overall_score": overall_score,
        "overall_grade": overall_grade,
        "topic_scores": topic_scores,
    }
