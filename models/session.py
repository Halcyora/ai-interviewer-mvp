from pydantic import BaseModel
from typing import Optional


class SessionCreate(BaseModel):
    company: str  # e.g., "google", "amazon", "meta", "apple", "netflix"
    role: str    # e.g., "software_engineer", "senior_software_engineer", etc.
    context_name: Optional[str] = None  # derived from company_role if not provided


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
