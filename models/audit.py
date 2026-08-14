from pydantic import BaseModel
from typing import List


class LLMAuditEntry(BaseModel):
    id: int
    session_id: str
    turn_id: int
    timestamp: str
    template_id: str
    model_id: str
    input_tokens: int
    output_tokens: int
    latency_ms: int
    entry_hash: str


class AuditTrailOut(BaseModel):
    session_id: str
    total_llm_calls: int
    total_rag_retrievals: int
    total_state_transitions: int
    llm_entries: List[LLMAuditEntry]
