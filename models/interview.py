from pydantic import BaseModel
from typing import Literal, Optional, List


class QuestionOut(BaseModel):
    session_id: str
    turn_index: int
    topic_id: str
    stretch_index: int
    question_text: str
    question_type: Literal["SEED", "FOLLOW_UP"]
    total_topics: int


class AnswerIn(BaseModel):
    session_id: str
    turn_index: int
    answer_text: str
    answer_mode: Literal["TEXT", "AUDIO"] = "TEXT"


class EvaluationOut(BaseModel):
    confidence_score: float
    reasoning: str
    key_points_covered: List[str]
    missing_points: List[str]
    next_action: Literal["FOLLOW_UP", "NEXT_TOPIC", "COMPLETED"]
    next_question: Optional[QuestionOut]
