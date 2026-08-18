from typing import List, Dict, Any

# Lenient grading thresholds (slightly lowered for fairness)
# Descending threshold order — first match wins
_GRADE_MAP = [(0.7, "A"), (0.5, "B"), (0.3, "C"), (0.1, "D"), (0.0, "F")]


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
    nova_lite_input_tokens: int,
    nova_lite_output_tokens: int,
    nova_pro_input_tokens: int,
    nova_pro_output_tokens: int,
) -> float:
    # Amazon Nova Lite pricing: $0.00015 per 1K input, $0.0006 per 1K output
    nova_lite = (nova_lite_input_tokens / 1000 * 0.00015) + (nova_lite_output_tokens / 1000 * 0.0006)
    # Amazon Nova Pro pricing: $0.0008 per 1K input, $0.0024 per 1K output
    nova_pro = (nova_pro_input_tokens / 1000 * 0.0008) + (nova_pro_output_tokens / 1000 * 0.0024)
    return round(nova_lite + nova_pro, 6)


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
