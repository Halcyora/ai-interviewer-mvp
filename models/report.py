from pydantic import BaseModel
from typing import List


class TopicBreakdown(BaseModel):
    topic_id: str
    topic_label: str
    avg_score: float
    grade: str
    num_questions: int


class ReportOut(BaseModel):
    session_id: str
    overall_score: float
    overall_grade: str
    strengths: List[str]
    gaps: List[str]
    narrative: str
    topic_breakdown: List[TopicBreakdown]
    total_cost_usd: float
    created_at: str
