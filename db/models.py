from sqlalchemy import Column, String, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id = Column(String, primary_key=True)           # UUID4
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    state = Column(String, nullable=False)          # IDLE|STARTED|QUESTIONING|AWAITING_ANSWER|EVALUATING|FOLLOW_UP|NEXT_TOPIC|COMPLETED
    context_name = Column(String, nullable=False)   # stem of context doc filename
    total_topics = Column(Integer, default=0)
    completed_topics = Column(Integer, default=0)
    overall_score = Column(Float, nullable=True)
    overall_grade = Column(String, nullable=True)
    estimated_cost_usd = Column(Float, default=0.0)
    different_question_count = Column(Integer, default=0)  # Track "ask different question" requests


class Turn(Base):
    __tablename__ = "turns"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    turn_index = Column(Integer, nullable=False)     # 0-based global counter
    topic_id = Column(String, nullable=False)
    stretch_index = Column(Integer, nullable=False)  # 0=seed Q, 1+=follow-up
    question_text = Column(Text, nullable=False)
    question_type = Column(String, nullable=False)   # SEED | FOLLOW_UP
    answer_text = Column(Text, nullable=True)
    answer_mode = Column(String, nullable=True)      # TEXT | AUDIO
    confidence_score = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    key_points_covered = Column(Text, nullable=True) # JSON array string
    missing_points = Column(Text, nullable=True)     # JSON array string
    created_at = Column(String, nullable=False)


class TopicScore(Base):
    __tablename__ = "topic_scores"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    topic_id = Column(String, nullable=False)
    topic_label = Column(String, nullable=False)
    num_questions = Column(Integer, nullable=False)
    avg_score = Column(Float, nullable=False)
    grade = Column(String, nullable=False)           # A|B|C|D|F


class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, unique=True)
    created_at = Column(String, nullable=False)
    overall_score = Column(Float, nullable=False)
    overall_grade = Column(String, nullable=False)
    strengths = Column(Text, nullable=False)         # JSON array string
    gaps = Column(Text, nullable=False)              # JSON array string
    narrative = Column(Text, nullable=False)
    topic_breakdown = Column(Text, nullable=False)   # JSON object string
    total_cost_usd = Column(Float, nullable=False)


# ── AUDIT TABLES (append-only — never UPDATE or DELETE) ──────────────────────

class LLMAuditLog(Base):
    __tablename__ = "llm_audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    turn_id = Column(Integer, nullable=False)         # -1 for report generation
    timestamp = Column(String, nullable=False)        # ISO 8601 UTC
    template_id = Column(String, nullable=False)      # EVALUATOR|FOLLOW_UP_GEN|REPORT_GEN
    model_id = Column(String, nullable=False)
    temperature = Column(Float, nullable=False)
    max_tokens = Column(Integer, nullable=False)
    prompt_hash = Column(String, nullable=False)      # SHA-256 hex of rendered prompt
    rendered_prompt = Column(Text, nullable=False)    # full prompt sent to LLM
    response_text = Column(Text, nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    prev_entry_hash = Column(String, nullable=False)  # "GENESIS" for first row
    entry_hash = Column(String, nullable=False)       # SHA-256 tamper-evident chain


class RAGAuditLog(Base):
    __tablename__ = "rag_audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    turn_id = Column(Integer, nullable=False)
    timestamp = Column(String, nullable=False)
    topic_id = Column(String, nullable=False)
    query_text = Column(Text, nullable=False)
    retrieved_chunk_ids = Column(Text, nullable=False) # JSON array string
    retrieved_scores = Column(Text, nullable=False)    # JSON array of floats string


class StateTransitionLog(Base):
    __tablename__ = "state_transition_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)
    old_state = Column(String, nullable=False)
    new_state = Column(String, nullable=False)
    reason = Column(String, nullable=False)            # QUESTION_PRESENTED|ANSWER_SUBMITTED|FOLLOW_UP_GENERATED|TOPIC_FINISHED|ALL_TOPICS_DONE
    confidence_score = Column(Float, nullable=True)
    stretch_count = Column(Integer, nullable=True)
