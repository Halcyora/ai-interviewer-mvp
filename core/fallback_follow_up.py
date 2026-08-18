"""
Fallback follow-up question generator when Bedrock is unavailable.
Generates simple follow-up questions based on context and missing points.
"""
import random


async def fallback_generate_follow_up(
    topic_label: str,
    original_question: str,
    candidate_answer: str,
    confidence_score: float,
    missing_points: list,
    context_chunks: str,
) -> str:
    """
    Generate a simple follow-up question without AWS.
    Uses templates and missing points to create contextual follow-ups.
    """
    templates = [
        "Can you elaborate more on {topic}?",
        "How would you apply {topic} in this scenario?",
        "What's your understanding of {topic}?",
        "Could you explain {topic} in more detail?",
        "How does {topic} relate to your previous answer?",
        "What are some examples of {topic}?",
        "Why is {topic} important here?",
        "Can you walk through an example involving {topic}?",
    ]
    
    # Use first missing point, or create generic follow-up
    if missing_points and len(missing_points) > 0:
        focus = missing_points[0]
    else:
        # Generic follow-up based on topic
        focus = topic_label.replace("_", " ").title()
    
    template = random.choice(templates)
    follow_up = template.format(topic=focus)
    
    return follow_up
