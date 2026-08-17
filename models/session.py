from pydantic import BaseModel
from typing import Literal, Optional


class SessionCreate(BaseModel):
    company: Optional[str] = None  # e.g., "google", "amazon", "meta", "apple", "netflix"
    role: Optional[str] = None    # e.g., "software_engineer", "senior_software_engineer", etc.
    context_name: Optional[str] = None  # can be provided directly by UI
    difficulty: Optional[Literal["beginner", "intermediate", "advanced"]] = None


class SessionOut(BaseModel):
    id: str
    state: str
    context_name: str
    total_topics: int
    completed_topics: int
    overall_score: Optional[float]
    overall_grade: Optional[str]
    estimated_cost_usd: float
    created_at: str
    updated_at: str
