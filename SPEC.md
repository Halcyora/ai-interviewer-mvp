# AI Interviewer MVP — AI-Executable Implementation Spec
> Status: READY_TO_IMPLEMENT
> Root: `c:\AI Interviewer MVP\` (all relative paths are from here)
> Python: 3.11+
> Last updated: 2026-08-14

---

## CROSS-CUTTING CONSTRAINTS
> Apply these in EVERY module. Non-negotiable.

### C1 — LOW LATENCY
- All I/O (DB, S3, Bedrock) is `async`; use `aiosqlite` + SQLAlchemy async engine
- ChromaDB collection is pre-loaded into memory at app startup (call `warmup()` in lifespan)
- Use **Claude 3.5 Haiku** (`bedrock_haiku_model_id`) for: evaluation, follow-up generation (fast, cheap)
- Use **Claude 3.5 Sonnet** (`bedrock_sonnet_model_id`) for: report generation only (quality needed)
- Seed questions are served directly — no LLM call needed (zero latency for first question)
- LRU cache on `get_collection()` and `get_bedrock_runtime()` — no re-init per request
- `max_tokens` hard caps: eval=256, follow_up=200, question_gen=512, report=1024
- Temperature: `0.0` for evaluation (deterministic), `0.7` for follow-up/question generation
- FastAPI `lifespan` warms ChromaDB HNSW index before first request

### C2 — LOW OPERATING COST
- **Never re-embed a chunk that already exists in ChromaDB**: check chunk_id before calling Bedrock
- Track `input_tokens` + `output_tokens` per Bedrock call → accumulate on `InterviewState`
- Per-session cost estimate: `compute_cost_usd(haiku_in, haiku_out, sonnet_in, sonnet_out)`
  - Haiku: $0.001/1K input, $0.005/1K output
  - Sonnet: $0.015/1K input, $0.075/1K output
- Audio billing: AWS Transcribe charged per 15 s; implement 2-second silence timeout to end stream early
- SQLite only — zero managed DB cost
- Single `uvicorn` process — no Lambda cold starts or API Gateway charges
- Sonnet used in exactly ONE place: `core/reporter.py`

### C3 — AUDITABILITY
- Every LLM call writes ONE row to `llm_audit_log` BEFORE returning result (non-optional)
- Tamper-evident chain: `entry_hash = SHA256(session_id|turn_id|timestamp|prompt_hash|response_text|prev_entry_hash)`
  - First row uses `prev_entry_hash = "GENESIS"`
  - Each subsequent row uses the `entry_hash` of the previous row for the same session
- RAG retrieval logged per turn: `rag_audit_log` stores chunk_ids + similarity scores
- Every state machine transition logged: `state_transition_log` stores old→new state + reason + confidence + stretch_count
- `GET /audit/{session_id}` returns full chronological audit trail
- `llm_audit_log`, `rag_audit_log`, `state_transition_log` are **append-only** — no `UPDATE` or `DELETE` ever
- All logs include: `session_id` (UUID), `turn_id` (int), `timestamp` (ISO 8601 UTC)

---

## 1. DIRECTORY SCAFFOLD

Create these directories and empty `__init__.py` files exactly as shown:

```
ai-interviewer-mvp/
├── data/
│   ├── context/                  ← user drops context docs here
│   └── questions/                ← user drops seed_questions.json here
├── rag/
│   ├── __init__.py
│   ├── chunker.py
│   ├── embeddings.py
│   ├── vectorstore.py
│   └── retriever.py
├── db/
│   ├── __init__.py
│   ├── database.py
│   ├── models.py
│   └── crud.py
├── core/
│   ├── __init__.py
│   ├── orchestrator.py
│   ├── evaluator.py
│   ├── follow_up.py
│   ├── scorer.py
│   ├── prompts.py
│   └── reporter.py
├── models/
│   ├── __init__.py
│   ├── session.py
│   ├── interview.py
│   ├── report.py
│   └── audit.py
├── api/
│   ├── __init__.py
│   ├── main.py
│   ├── websocket.py
│   └── routes/
│       ├── __init__.py
│       ├── interview.py
│       ├── sessions.py
│       ├── reports.py
│       └── audit.py
├── ui/
│   ├── static/
│   │   ├── app.js
│   │   └── style.css
│   └── templates/
│       ├── index.html
│       └── report.html
├── config/
│   ├── __init__.py
│   ├── settings.py
│   └── aws.py
├── scripts/
│   ├── __init__.py
│   └── ingest.py
├── requirements.txt
└── .env.example
```

---

## 2. `requirements.txt`

```
fastapi==0.115.0
uvicorn[standard]==0.30.6
python-dotenv==1.0.1
pydantic==2.8.2
pydantic-settings==2.4.0
sqlalchemy==2.0.35
aiosqlite==0.20.0
greenlet==3.1.1
langchain==0.3.1
langchain-community==0.3.1
langchain-aws==0.2.2
chromadb==0.5.11
boto3==1.35.22
amazon-transcribe==0.6.2
jinja2==3.1.4
python-multipart==0.0.9
pypdf==4.3.1
python-docx==1.1.2
aiofiles==24.1.0
httpx==0.27.2
```

---

## 3. `.env.example`

```
AWS_ACCESS_KEY_ID=your_key_here
AWS_SECRET_ACCESS_KEY=your_secret_here
AWS_DEFAULT_REGION=us-east-1
BEDROCK_HAIKU_MODEL_ID=anthropic.claude-3-5-haiku-20241022-v1:0
BEDROCK_SONNET_MODEL_ID=anthropic.claude-3-5-sonnet-20241022-v2:0
BEDROCK_EMBED_MODEL_ID=amazon.titan-embed-text-v2:0
CHROMA_PERSIST_DIR=./chroma_db
SQLITE_DB_PATH=./interview.db
TOP_K=5
CHUNK_SIZE=512
CHUNK_OVERLAP=50
FOLLOW_UP_THRESHOLD_LOW=0.4
FOLLOW_UP_THRESHOLD_HIGH=0.8
MAX_STRETCH_COUNT=3
AUDIO_SILENCE_TIMEOUT_SEC=2.0
LOG_LEVEL=INFO
```

---

## 4. `config/settings.py`

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_access_key_id: str
    aws_secret_access_key: str
    aws_default_region: str = "us-east-1"
    bedrock_haiku_model_id: str = "anthropic.claude-3-5-haiku-20241022-v1:0"
    bedrock_sonnet_model_id: str = "anthropic.claude-3-5-sonnet-20241022-v2:0"
    bedrock_embed_model_id: str = "amazon.titan-embed-text-v2:0"
    chroma_persist_dir: str = "./chroma_db"
    sqlite_db_path: str = "./interview.db"
    top_k: int = 5
    chunk_size: int = 512
    chunk_overlap: int = 50
    follow_up_threshold_low: float = 0.4
    follow_up_threshold_high: float = 0.8
    max_stretch_count: int = 3
    audio_silence_timeout_sec: float = 2.0
    log_level: str = "INFO"

settings = Settings()
```

---

## 5. `config/aws.py`

```python
import boto3
from functools import lru_cache
from config.settings import settings

@lru_cache(maxsize=1)
def get_bedrock_runtime() -> boto3.client:
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_default_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )

@lru_cache(maxsize=1)
def get_transcribe_client() -> boto3.client:
    return boto3.client(
        "transcribestreaming",
        region_name=settings.aws_default_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
```

---

## 6. `db/models.py`

Seven tables. PKs are UUID strings (sessions) or autoincrement ints. Timestamps are ISO 8601 UTC strings.
`llm_audit_log`, `rag_audit_log`, `state_transition_log` are **append-only**.

```python
from sqlalchemy import Column, String, Float, Integer, Text
from sqlalchemy.orm import DeclarativeBase

class Base(DeclarativeBase):
    pass

class InterviewSession(Base):
    __tablename__ = "interview_sessions"
    id = Column(String, primary_key=True)            # UUID4
    created_at = Column(String, nullable=False)
    updated_at = Column(String, nullable=False)
    state = Column(String, nullable=False)           # IDLE|STARTED|QUESTIONING|AWAITING_ANSWER|EVALUATING|FOLLOW_UP|NEXT_TOPIC|COMPLETED
    context_name = Column(String, nullable=False)    # stem of context doc filename
    total_topics = Column(Integer, default=0)
    completed_topics = Column(Integer, default=0)
    overall_score = Column(Float, nullable=True)
    overall_grade = Column(String, nullable=True)
    estimated_cost_usd = Column(Float, default=0.0)

class Turn(Base):
    __tablename__ = "turns"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    turn_index = Column(Integer, nullable=False)      # 0-based global counter
    topic_id = Column(String, nullable=False)
    stretch_index = Column(Integer, nullable=False)   # 0=seed Q, 1+=follow-up
    question_text = Column(Text, nullable=False)
    question_type = Column(String, nullable=False)    # SEED | FOLLOW_UP
    answer_text = Column(Text, nullable=True)
    answer_mode = Column(String, nullable=True)       # TEXT | AUDIO
    confidence_score = Column(Float, nullable=True)
    reasoning = Column(Text, nullable=True)
    key_points_covered = Column(Text, nullable=True)  # JSON array string
    missing_points = Column(Text, nullable=True)      # JSON array string
    created_at = Column(String, nullable=False)

class TopicScore(Base):
    __tablename__ = "topic_scores"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    topic_id = Column(String, nullable=False)
    topic_label = Column(String, nullable=False)
    num_questions = Column(Integer, nullable=False)
    avg_score = Column(Float, nullable=False)
    grade = Column(String, nullable=False)            # A|B|C|D|F

class Report(Base):
    __tablename__ = "reports"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, unique=True)
    created_at = Column(String, nullable=False)
    overall_score = Column(Float, nullable=False)
    overall_grade = Column(String, nullable=False)
    strengths = Column(Text, nullable=False)          # JSON array string
    gaps = Column(Text, nullable=False)               # JSON array string
    narrative = Column(Text, nullable=False)
    topic_breakdown = Column(Text, nullable=False)    # JSON object string
    total_cost_usd = Column(Float, nullable=False)

# ── AUDIT TABLES (append-only) ────────────────────────────────────────────────

class LLMAuditLog(Base):
    __tablename__ = "llm_audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    turn_id = Column(Integer, nullable=False)          # -1 for report generation
    timestamp = Column(String, nullable=False)         # ISO 8601 UTC
    template_id = Column(String, nullable=False)       # EVALUATOR|FOLLOW_UP_GEN|REPORT_GEN
    model_id = Column(String, nullable=False)
    temperature = Column(Float, nullable=False)
    max_tokens = Column(Integer, nullable=False)
    prompt_hash = Column(String, nullable=False)       # SHA-256 hex of rendered prompt
    rendered_prompt = Column(Text, nullable=False)     # full prompt sent to LLM
    response_text = Column(Text, nullable=False)
    input_tokens = Column(Integer, nullable=False)
    output_tokens = Column(Integer, nullable=False)
    latency_ms = Column(Integer, nullable=False)
    prev_entry_hash = Column(String, nullable=False)   # "GENESIS" for first row
    entry_hash = Column(String, nullable=False)        # SHA-256 tamper-evident chain

class RAGAuditLog(Base):
    __tablename__ = "rag_audit_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    turn_id = Column(Integer, nullable=False)
    timestamp = Column(String, nullable=False)
    topic_id = Column(String, nullable=False)
    query_text = Column(Text, nullable=False)
    retrieved_chunk_ids = Column(Text, nullable=False)  # JSON array string
    retrieved_scores = Column(Text, nullable=False)     # JSON array of floats string

class StateTransitionLog(Base):
    __tablename__ = "state_transition_log"
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False)
    timestamp = Column(String, nullable=False)
    old_state = Column(String, nullable=False)
    new_state = Column(String, nullable=False)
    reason = Column(String, nullable=False)             # QUESTION_PRESENTED|ANSWER_SUBMITTED|SCORE_HIGH|SCORE_LOW|SCORE_PARTIAL|STRETCH_LIMIT|ALL_TOPICS_DONE
    confidence_score = Column(Float, nullable=True)
    stretch_count = Column(Integer, nullable=True)
```

---

## 7. `db/database.py`

```python
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from config.settings import settings
from db.models import Base

engine = create_async_engine(
    f"sqlite+aiosqlite:///{settings.sqlite_db_path}",
    echo=False,
    connect_args={"check_same_thread": False},
)

AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

async def get_db():
    async with AsyncSessionLocal() as session:
        yield session
```

---

## 8. `db/crud.py`

All DB operations. Audit tables use only `INSERT` — never `UPDATE`/`DELETE`.

```python
import hashlib
import json
from datetime import datetime, timezone
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from db.models import (
    InterviewSession, Turn, TopicScore, Report,
    LLMAuditLog, RAGAuditLog, StateTransitionLog,
)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _audit_hash(session_id, turn_id, timestamp, prompt_hash, response_text, prev_hash) -> str:
    raw = f"{session_id}|{turn_id}|{timestamp}|{prompt_hash}|{response_text}|{prev_hash}"
    return hashlib.sha256(raw.encode()).hexdigest()

# ── Session ──────────────────────────────────────────────────────────────────

async def create_session(db: AsyncSession, session_id: str, context_name: str, total_topics: int) -> InterviewSession:
    now = _now()
    row = InterviewSession(
        id=session_id, created_at=now, updated_at=now,
        state="STARTED", context_name=context_name, total_topics=total_topics,
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row

async def update_session_state(db: AsyncSession, session_id: str, state: str, **kwargs):
    result = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    row = result.scalar_one()
    row.state = state
    row.updated_at = _now()
    for k, v in kwargs.items():
        setattr(row, k, v)
    await db.commit()

# ── Turn ─────────────────────────────────────────────────────────────────────

async def create_turn(
    db: AsyncSession, session_id: str, turn_index: int, topic_id: str,
    stretch_index: int, question_text: str, question_type: str,
) -> int:
    row = Turn(
        session_id=session_id, turn_index=turn_index, topic_id=topic_id,
        stretch_index=stretch_index, question_text=question_text,
        question_type=question_type, created_at=_now(),
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row.id

async def update_turn_answer(
    db: AsyncSession, turn_id: int, answer_text: str, answer_mode: str, eval_result: dict
):
    result = await db.execute(select(Turn).where(Turn.id == turn_id))
    row = result.scalar_one()
    row.answer_text = answer_text
    row.answer_mode = answer_mode
    row.confidence_score = eval_result["score"]
    row.reasoning = eval_result["reasoning"]
    row.key_points_covered = json.dumps(eval_result["key_points_covered"])
    row.missing_points = json.dumps(eval_result["missing_points"])
    await db.commit()

async def get_all_turns(db: AsyncSession, session_id: str) -> list:
    result = await db.execute(
        select(Turn).where(Turn.session_id == session_id).order_by(Turn.turn_index)
    )
    return result.scalars().all()

# ── Topic Score ───────────────────────────────────────────────────────────────

async def upsert_topic_score(
    db: AsyncSession, session_id: str, topic_id: str, topic_label: str,
    num_q: int, avg_score: float, grade: str,
):
    row = TopicScore(
        session_id=session_id, topic_id=topic_id, topic_label=topic_label,
        num_questions=num_q, avg_score=avg_score, grade=grade,
    )
    db.add(row)
    await db.commit()

async def get_topic_scores(db: AsyncSession, session_id: str) -> list:
    result = await db.execute(select(TopicScore).where(TopicScore.session_id == session_id))
    return result.scalars().all()

# ── Report ────────────────────────────────────────────────────────────────────

async def save_report(db: AsyncSession, report: dict) -> Report:
    row = Report(
        session_id=report["session_id"],
        created_at=_now(),
        overall_score=report["overall_score"],
        overall_grade=report["overall_grade"],
        strengths=json.dumps(report["strengths"]),
        gaps=json.dumps(report["gaps"]),
        narrative=report["narrative"],
        topic_breakdown=json.dumps(report["topic_breakdown"]),
        total_cost_usd=report["total_cost_usd"],
    )
    db.add(row)
    await db.commit()
    await db.refresh(row)
    return row

# ── Audit (append-only) ───────────────────────────────────────────────────────

async def append_llm_audit(
    db: AsyncSession, session_id: str, turn_id: int, template_id: str,
    model_id: str, temperature: float, max_tokens: int, rendered_prompt: str,
    response_text: str, input_tokens: int, output_tokens: int,
    latency_ms: int, prev_entry_hash: str,
) -> str:
    timestamp = _now()
    prompt_hash = hashlib.sha256(rendered_prompt.encode()).hexdigest()
    entry_hash = _audit_hash(session_id, turn_id, timestamp, prompt_hash, response_text, prev_entry_hash)
    row = LLMAuditLog(
        session_id=session_id, turn_id=turn_id, timestamp=timestamp,
        template_id=template_id, model_id=model_id, temperature=temperature,
        max_tokens=max_tokens, prompt_hash=prompt_hash, rendered_prompt=rendered_prompt,
        response_text=response_text, input_tokens=input_tokens, output_tokens=output_tokens,
        latency_ms=latency_ms, prev_entry_hash=prev_entry_hash, entry_hash=entry_hash,
    )
    db.add(row)
    await db.commit()
    return entry_hash

async def get_last_audit_hash(db: AsyncSession, session_id: str) -> str:
    result = await db.execute(
        select(LLMAuditLog.entry_hash)
        .where(LLMAuditLog.session_id == session_id)
        .order_by(LLMAuditLog.id.desc())
        .limit(1)
    )
    row = result.scalar_one_or_none()
    return row if row else "GENESIS"

async def log_rag_retrieval(
    db: AsyncSession, session_id: str, turn_id: int, topic_id: str,
    query_text: str, chunk_ids: list, scores: list,
):
    row = RAGAuditLog(
        session_id=session_id, turn_id=turn_id, timestamp=_now(),
        topic_id=topic_id, query_text=query_text,
        retrieved_chunk_ids=json.dumps(chunk_ids),
        retrieved_scores=json.dumps(scores),
    )
    db.add(row)
    await db.commit()

async def log_state_transition(
    db: AsyncSession, session_id: str, old_state: str, new_state: str,
    reason: str, confidence_score, stretch_count,
):
    row = StateTransitionLog(
        session_id=session_id, timestamp=_now(),
        old_state=old_state, new_state=new_state, reason=reason,
        confidence_score=confidence_score, stretch_count=stretch_count,
    )
    db.add(row)
    await db.commit()
```

---

## 9. `models/session.py`

```python
from pydantic import BaseModel
from typing import Optional

class SessionCreate(BaseModel):
    context_name: str   # must match stem of seed_questions.json filename

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
```

---

## 10. `models/interview.py`

```python
from pydantic import BaseModel
from typing import Literal, Optional, List

class QuestionOut(BaseModel):
    session_id: str
    turn_index: int
    topic_id: str
    stretch_index: int
    question_text: str
    question_type: Literal["SEED", "FOLLOW_UP"]

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
```

---

## 11. `models/report.py`

```python
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
```

---

## 12. `models/audit.py`

```python
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
```

---

## 13. `data/questions/` — Seed Questions JSON Schema

File naming convention: `{context_name}_questions.json`
Example: `my_context_questions.json` for `context_name = "my_context"`

```json
{
  "context_name": "my_context",
  "topics": [
    {
      "topic_id": "topic_001",
      "topic_label": "Self-Attention Mechanism",
      "seed_question": "Can you explain how self-attention works in transformer models?",
      "expected_key_points": [
        "query, key, value vectors",
        "scaled dot-product attention",
        "softmax normalization",
        "multi-head attention"
      ]
    },
    {
      "topic_id": "topic_002",
      "topic_label": "Positional Encoding",
      "seed_question": "Why is positional encoding necessary in transformers?",
      "expected_key_points": [
        "transformers have no recurrence",
        "sine and cosine functions",
        "relative position information"
      ]
    }
  ]
}
```

Field rules:
- `topic_id`: unique slug, no spaces
- `topic_label`: human-readable label shown in UI and report
- `seed_question`: verbatim question shown to the user (no LLM call needed)
- `expected_key_points`: concepts used by the evaluator prompt and follow-up generator

---

## 14. `rag/chunker.py`

```python
import hashlib
from pathlib import Path
from typing import List
from langchain.text_splitter import RecursiveCharacterTextSplitter
from config.settings import settings

def load_document(file_path: str) -> str:
    """Loads PDF, DOCX, or plain text. Returns raw text string."""
    path = Path(file_path)
    if path.suffix == ".pdf":
        from pypdf import PdfReader
        reader = PdfReader(file_path)
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    elif path.suffix == ".docx":
        from docx import Document
        doc = Document(file_path)
        return "\n".join(p.text for p in doc.paragraphs)
    else:
        return path.read_text(encoding="utf-8")

def chunk_text(text: str, source: str) -> List[dict]:
    """Returns list of {chunk_id, text, source, char_start}."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=settings.chunk_size,
        chunk_overlap=settings.chunk_overlap,
        add_start_index=True,
    )
    docs = splitter.create_documents([text], metadatas=[{"source": source}])
    chunks = []
    for i, doc in enumerate(docs):
        # deterministic ID: prevents re-embedding identical content
        chunk_hash = hashlib.sha256(doc.page_content.encode()).hexdigest()[:16]
        chunks.append({
            "chunk_id": f"{source}__{i}__{chunk_hash}",
            "text": doc.page_content,
            "source": source,
            "char_start": doc.metadata.get("start_index", 0),
        })
    return chunks
```

---

## 15. `rag/embeddings.py`

```python
import json
from typing import List
from config.settings import settings
from config.aws import get_bedrock_runtime

def embed_texts(texts: List[str]) -> List[List[float]]:
    """Batch embed via AWS Titan Embeddings v2. Returns 1024-dim vectors."""
    client = get_bedrock_runtime()
    embeddings = []
    for text in texts:
        body = json.dumps({"inputText": text, "dimensions": 1024, "normalize": True})
        response = client.invoke_model(
            modelId=settings.bedrock_embed_model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        result = json.loads(response["body"].read())
        embeddings.append(result["embedding"])
    return embeddings

def embed_single(text: str) -> List[float]:
    return embed_texts([text])[0]
```

---

## 16. `rag/vectorstore.py`

```python
import chromadb
from chromadb.config import Settings as ChromaSettings
from typing import List
from config.settings import settings

_collection = None
COLLECTION_NAME = "interview_context"

def get_collection() -> chromadb.Collection:
    global _collection
    if _collection is None:
        client = chromadb.PersistentClient(
            path=settings.chroma_persist_dir,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine"},
        )
    return _collection

def upsert_chunks(chunks: List[dict], embeddings: List[List[float]]) -> int:
    """Upserts only NEW chunks (C2: never re-embed existing). Returns count inserted."""
    collection = get_collection()
    existing_ids = set(collection.get(ids=[c["chunk_id"] for c in chunks])["ids"])
    new_pairs = [(c, e) for c, e in zip(chunks, embeddings) if c["chunk_id"] not in existing_ids]
    if not new_pairs:
        return 0
    collection.upsert(
        ids=[c["chunk_id"] for c, _ in new_pairs],
        embeddings=[e for _, e in new_pairs],
        documents=[c["text"] for c, _ in new_pairs],
        metadatas=[{"source": c["source"], "char_start": c["char_start"]} for c, _ in new_pairs],
    )
    return len(new_pairs)

def warmup() -> None:
    """Pre-load HNSW index into memory at startup (C1: latency)."""
    col = get_collection()
    _ = col.count()
```

---

## 17. `rag/retriever.py`

```python
from typing import List, Tuple
from rag.vectorstore import get_collection
from rag.embeddings import embed_single
from config.settings import settings

def retrieve(query: str, k: int | None = None) -> List[Tuple[str, str, float]]:
    """Returns [(chunk_id, text, similarity_score)] sorted descending by score."""
    k = k or settings.top_k
    collection = get_collection()
    query_vec = embed_single(query)
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=k,
        include=["documents", "distances"],
    )
    return [
        (cid, doc, round(1.0 - dist, 4))
        for cid, doc, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["distances"][0],
        )
    ]
```

---

## 18. `scripts/ingest.py`

```python
"""
Usage: python -m scripts.ingest --context data/context/my_doc.pdf
Loads a context document, chunks it, embeds via Bedrock, and stores in ChromaDB.
Re-running is safe — existing chunks are skipped (C2: no re-embedding cost).
"""
import argparse
from pathlib import Path
from rag.chunker import load_document, chunk_text
from rag.embeddings import embed_texts
from rag.vectorstore import upsert_chunks

def main():
    parser = argparse.ArgumentParser(description="Ingest context document into ChromaDB")
    parser.add_argument("--context", required=True, help="Path to .pdf / .docx / .txt")
    args = parser.parse_args()
    path = Path(args.context)
    if not path.exists():
        raise FileNotFoundError(f"Context file not found: {path}")
    print(f"Loading {path.name}...")
    text = load_document(str(path))
    chunks = chunk_text(text, path.stem)
    print(f"  → {len(chunks)} chunks. Embedding new chunks only...")
    embeddings = embed_texts([c["text"] for c in chunks])
    inserted = upsert_chunks(chunks, embeddings)
    skipped = len(chunks) - inserted
    print(f"  → {inserted} inserted, {skipped} skipped (already cached). Done.")

if __name__ == "__main__":
    main()
```

---

## 19. `core/prompts.py`

All four prompt templates. Use Python `.format(**kwargs)` at call sites.
Note: double-braces `{{}}` are literal curly braces in the output (not format slots).

```python
# Haiku (fast, cheap): not used here — seed question is served directly from JSON
# Haiku: evaluation, follow-up generation
# Sonnet: report generation only

EVALUATOR = """\
You are an expert technical interviewer evaluating a candidate's answer.

TOPIC: {topic_label}
QUESTION: {question_text}
EXPECTED KEY POINTS: {expected_key_points}
CONTEXT (ground truth):
{context_chunks}
CANDIDATE'S ANSWER: {candidate_answer}

Evaluate and return ONLY valid JSON matching this exact schema:
{{
  "score": <float 0.0 to 1.0>,
  "reasoning": "<one sentence explaining the score>",
  "key_points_covered": ["<point>", "..."],
  "missing_points": ["<point>", "..."]
}}

Scoring rubric:
  0.0–0.3 → Incorrect or irrelevant
  0.4–0.6 → Partial, missing key concepts
  0.6–0.8 → Good but incomplete
  0.8–1.0 → Comprehensive and accurate

Return ONLY the JSON object. No markdown fences, no preamble.
"""

FOLLOW_UP_GEN = """\
You are a professional technical interviewer conducting a follow-up question.

TOPIC: {topic_label}
ORIGINAL QUESTION: {original_question}
CANDIDATE'S ANSWER: {candidate_answer}
CONFIDENCE SCORE: {confidence_score}
MISSING POINTS: {missing_points}

CONTEXT EXCERPTS:
{context_chunks}

Instructions:
- Ask exactly ONE follow-up question that probes the missing points
- Do NOT repeat the original question verbatim
- Do NOT reveal expected answers
- Output ONLY the follow-up question text, nothing else.
"""

REPORT_GEN = """\
You are a senior hiring manager writing a post-interview assessment report.

INTERVIEW SUMMARY:
{interview_summary_json}

Write a professional assessment. Return ONLY valid JSON matching this exact schema:
{{
  "narrative": "<2–3 paragraph narrative summarising overall performance>",
  "strengths": ["<strength1>", "..."],
  "gaps": ["<gap1>", "..."]
}}

Return ONLY the JSON object. No markdown fences, no preamble.
"""
```

---

## 20. `core/scorer.py`

```python
from typing import List

# (threshold, grade) in descending order
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
    haiku_input_tokens: int, haiku_output_tokens: int,
    sonnet_input_tokens: int, sonnet_output_tokens: int,
) -> float:
    haiku = (haiku_input_tokens / 1000 * 0.001) + (haiku_output_tokens / 1000 * 0.005)
    sonnet = (sonnet_input_tokens / 1000 * 0.015) + (sonnet_output_tokens / 1000 * 0.075)
    return round(haiku + sonnet, 6)
```

---

## 21. `core/evaluator.py`

```python
import json
import time
from config.settings import settings
from config.aws import get_bedrock_runtime
from core.prompts import EVALUATOR
from db.crud import append_llm_audit

async def evaluate_answer(
    session_id: str,
    turn_id: int,
    topic_label: str,
    question_text: str,
    expected_key_points: list,
    context_chunks: str,
    candidate_answer: str,
    prev_entry_hash: str,
    db,
) -> dict:
    """
    Returns {score, reasoning, key_points_covered, missing_points}.
    Writes audit row before returning (C3).
    Uses Haiku for low latency + cost (C1, C2).
    """
    rendered = EVALUATOR.format(
        topic_label=topic_label,
        question_text=question_text,
        expected_key_points=json.dumps(expected_key_points),
        context_chunks=context_chunks,
        candidate_answer=candidate_answer,
    )
    response_text, meta = _invoke_bedrock(
        rendered,
        model_id=settings.bedrock_haiku_model_id,
        max_tokens=256,
        temperature=0.0,
    )
    await append_llm_audit(
        db=db, session_id=session_id, turn_id=turn_id,
        template_id="EVALUATOR", model_id=settings.bedrock_haiku_model_id,
        temperature=0.0, max_tokens=256, rendered_prompt=rendered,
        response_text=response_text, input_tokens=meta["input_tokens"],
        output_tokens=meta["output_tokens"], latency_ms=meta["latency_ms"],
        prev_entry_hash=prev_entry_hash,
    )
    return json.loads(response_text)

def _invoke_bedrock(prompt: str, model_id: str, max_tokens: int, temperature: float) -> tuple:
    """Returns (response_text, {input_tokens, output_tokens, latency_ms})."""
    client = get_bedrock_runtime()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "messages": [{"role": "user", "content": prompt}],
    })
    t0 = time.monotonic()
    response = client.invoke_model(
        modelId=model_id, body=body,
        contentType="application/json", accept="application/json",
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    resp_body = json.loads(response["body"].read())
    text = resp_body["content"][0]["text"]
    usage = resp_body.get("usage", {})
    return text, {
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "latency_ms": latency_ms,
    }
```

---

## 22. `core/follow_up.py`

```python
import json
import time
from config.settings import settings
from config.aws import get_bedrock_runtime
from core.prompts import FOLLOW_UP_GEN
from db.crud import append_llm_audit

def should_follow_up(confidence_score: float, stretch_count: int) -> str:
    """
    Returns 'FOLLOW_UP' or 'NEXT_TOPIC'.
    stretch_count is 1-based (1 = seed Q answered, 2 = first follow-up answered, etc.)
    Max stretch = settings.max_stretch_count (default 3).
    """
    in_partial_range = (
        settings.follow_up_threshold_low
        <= confidence_score
        <= settings.follow_up_threshold_high
    )
    under_limit = stretch_count < settings.max_stretch_count
    if in_partial_range and under_limit:
        return "FOLLOW_UP"
    return "NEXT_TOPIC"

async def generate_follow_up(
    session_id: str,
    turn_id: int,
    topic_label: str,
    original_question: str,
    candidate_answer: str,
    confidence_score: float,
    missing_points: list,
    context_chunks: str,
    prev_entry_hash: str,
    db,
) -> str:
    """Returns follow-up question text. Uses Haiku (C1, C2). Writes audit row (C3)."""
    rendered = FOLLOW_UP_GEN.format(
        topic_label=topic_label,
        original_question=original_question,
        candidate_answer=candidate_answer,
        confidence_score=confidence_score,
        missing_points=json.dumps(missing_points),
        context_chunks=context_chunks,
    )
    client = get_bedrock_runtime()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 200,
        "temperature": 0.7,
        "messages": [{"role": "user", "content": rendered}],
    })
    t0 = time.monotonic()
    response = client.invoke_model(
        modelId=settings.bedrock_haiku_model_id, body=body,
        contentType="application/json", accept="application/json",
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    resp_body = json.loads(response["body"].read())
    text = resp_body["content"][0]["text"].strip()
    usage = resp_body.get("usage", {})
    await append_llm_audit(
        db=db, session_id=session_id, turn_id=turn_id,
        template_id="FOLLOW_UP_GEN", model_id=settings.bedrock_haiku_model_id,
        temperature=0.7, max_tokens=200, rendered_prompt=rendered,
        response_text=text, input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0), latency_ms=latency_ms,
        prev_entry_hash=prev_entry_hash,
    )
    return text
```

---

## 23. `core/orchestrator.py`

```python
"""
One InterviewState instance lives in-memory per active session (keyed by session_id).
State machine transitions:
  STARTED → AWAITING_ANSWER (get_next_question)
  AWAITING_ANSWER → EVALUATING (submit_answer called)
  EVALUATING → FOLLOW_UP → AWAITING_ANSWER  (partial score, stretch < limit)
  EVALUATING → NEXT_TOPIC → AWAITING_ANSWER  (high/low score or stretch limit)
  NEXT_TOPIC → COMPLETED  (no more topics)
"""
from dataclasses import dataclass, field
from typing import List, Optional
from core.evaluator import evaluate_answer
from core.follow_up import should_follow_up, generate_follow_up
from core.scorer import compute_topic_score, score_to_grade
from rag.retriever import retrieve
from db.crud import (
    create_turn, update_turn_answer, upsert_topic_score,
    log_rag_retrieval, log_state_transition, get_last_audit_hash,
)

@dataclass
class TopicState:
    topic_id: str
    topic_label: str
    seed_question: str
    expected_key_points: List[str]
    stretch_count: int = 0         # increments with each Q in this stretch (1-based after first Q asked)
    scores: List[float] = field(default_factory=list)
    current_question: str = ""
    context_chunks: str = ""
    current_turn_db_id: int = 0    # Turn.id from DB

@dataclass
class InterviewState:
    session_id: str
    state: str
    topics: List[TopicState]
    current_topic_index: int = 0
    global_turn_index: int = 0     # 0-based, increments after each answer submitted
    haiku_input_tokens: int = 0
    haiku_output_tokens: int = 0
    sonnet_input_tokens: int = 0
    sonnet_output_tokens: int = 0

_sessions: dict[str, InterviewState] = {}

def load_session(session_id: str) -> Optional[InterviewState]:
    return _sessions.get(session_id)

def init_session(session_id: str, topics_json: List[dict]) -> InterviewState:
    topics = [
        TopicState(
            topic_id=t["topic_id"],
            topic_label=t["topic_label"],
            seed_question=t["seed_question"],
            expected_key_points=t["expected_key_points"],
        )
        for t in topics_json
    ]
    state = InterviewState(session_id=session_id, state="STARTED", topics=topics)
    _sessions[session_id] = state
    return state

async def get_next_question(session_id: str, db) -> dict:
    """RAG retrieval + serve seed question. Advances state to AWAITING_ANSWER."""
    s = _sessions[session_id]
    topic = s.topics[s.current_topic_index]

    # RAG: retrieve top-k chunks for this topic's seed question (C1: cached after warmup)
    results = retrieve(topic.seed_question)
    topic.context_chunks = "\n\n---\n\n".join(r[1] for r in results)
    await log_rag_retrieval(
        db, s.session_id, s.global_turn_index, topic.topic_id,
        topic.seed_question, [r[0] for r in results], [r[2] for r in results],
    )

    # Serve seed question directly — no LLM call (C1: zero latency, C2: zero cost)
    topic.current_question = topic.seed_question
    topic.stretch_count = 1

    turn_db_id = await create_turn(
        db, s.session_id, s.global_turn_index,
        topic.topic_id, 0, topic.current_question, "SEED",
    )
    topic.current_turn_db_id = turn_db_id

    old_state = s.state
    s.state = "AWAITING_ANSWER"
    await log_state_transition(db, s.session_id, old_state, "AWAITING_ANSWER", "QUESTION_PRESENTED", None, None)

    return {
        "session_id": s.session_id,
        "turn_index": s.global_turn_index,
        "topic_id": topic.topic_id,
        "stretch_index": 0,
        "question_text": topic.current_question,
        "question_type": "SEED",
    }

async def submit_answer(session_id: str, answer_text: str, answer_mode: str, db) -> dict:
    """Evaluate answer → decide follow-up or next topic → return next action + question."""
    s = _sessions[session_id]
    topic = s.topics[s.current_topic_index]

    s.state = "EVALUATING"
    await log_state_transition(db, s.session_id, "AWAITING_ANSWER", "EVALUATING", "ANSWER_SUBMITTED", None, None)

    prev_hash = await get_last_audit_hash(db, s.session_id)
    eval_result = await evaluate_answer(
        session_id=s.session_id, turn_id=topic.current_turn_db_id,
        topic_label=topic.topic_label, question_text=topic.current_question,
        expected_key_points=topic.expected_key_points,
        context_chunks=topic.context_chunks, candidate_answer=answer_text,
        prev_entry_hash=prev_hash, db=db,
    )

    score: float = eval_result["score"]
    topic.scores.append(score)
    await update_turn_answer(db, topic.current_turn_db_id, answer_text, answer_mode, eval_result)
    s.global_turn_index += 1

    next_action = should_follow_up(score, topic.stretch_count)

    if next_action == "FOLLOW_UP":
        s.state = "FOLLOW_UP"
        prev_hash = await get_last_audit_hash(db, s.session_id)
        follow_up_text = await generate_follow_up(
            session_id=s.session_id, turn_id=s.global_turn_index,
            topic_label=topic.topic_label, original_question=topic.current_question,
            candidate_answer=answer_text, confidence_score=score,
            missing_points=eval_result["missing_points"],
            context_chunks=topic.context_chunks,
            prev_entry_hash=prev_hash, db=db,
        )
        topic.current_question = follow_up_text
        topic.stretch_count += 1

        turn_db_id = await create_turn(
            db, s.session_id, s.global_turn_index, topic.topic_id,
            topic.stretch_count - 1, follow_up_text, "FOLLOW_UP",
        )
        topic.current_turn_db_id = turn_db_id
        s.state = "AWAITING_ANSWER"
        await log_state_transition(
            db, s.session_id, "FOLLOW_UP", "AWAITING_ANSWER",
            "FOLLOW_UP_GENERATED", score, topic.stretch_count,
        )
        return {
            "confidence_score": score,
            "reasoning": eval_result["reasoning"],
            "key_points_covered": eval_result["key_points_covered"],
            "missing_points": eval_result["missing_points"],
            "next_action": "FOLLOW_UP",
            "next_question": {
                "session_id": s.session_id,
                "turn_index": s.global_turn_index,
                "topic_id": topic.topic_id,
                "stretch_index": topic.stretch_count - 1,
                "question_text": follow_up_text,
                "question_type": "FOLLOW_UP",
            },
        }
    else:
        # Save topic score and advance topic
        topic_avg = compute_topic_score(topic.scores)
        grade = score_to_grade(topic_avg)
        await upsert_topic_score(
            db, s.session_id, topic.topic_id, topic.topic_label,
            len(topic.scores), topic_avg, grade,
        )
        s.current_topic_index += 1

        if s.current_topic_index >= len(s.topics):
            s.state = "COMPLETED"
            await log_state_transition(
                db, s.session_id, "NEXT_TOPIC", "COMPLETED", "ALL_TOPICS_DONE", score, topic.stretch_count,
            )
            return {
                "confidence_score": score,
                "reasoning": eval_result["reasoning"],
                "key_points_covered": eval_result["key_points_covered"],
                "missing_points": eval_result["missing_points"],
                "next_action": "COMPLETED",
                "next_question": None,
            }
        else:
            s.state = "NEXT_TOPIC"
            await log_state_transition(
                db, s.session_id, "EVALUATING", "NEXT_TOPIC", "TOPIC_FINISHED", score, topic.stretch_count,
            )
            next_q = await get_next_question(session_id, db)
            return {
                "confidence_score": score,
                "reasoning": eval_result["reasoning"],
                "key_points_covered": eval_result["key_points_covered"],
                "missing_points": eval_result["missing_points"],
                "next_action": "NEXT_TOPIC",
                "next_question": next_q,
            }
```

---

## 24. `core/reporter.py`

```python
import json
import time
from config.settings import settings
from config.aws import get_bedrock_runtime
from core.prompts import REPORT_GEN
from core.scorer import compute_overall_score, score_to_grade, compute_cost_usd
from db.crud import append_llm_audit, get_last_audit_hash, get_topic_scores, get_all_turns

async def generate_report(session_id: str, orchestrator_state, db) -> dict:
    """Uses Sonnet (C1: quality for report). Writes audit row (C3)."""
    topic_score_rows = await get_topic_scores(db, session_id)
    turns = await get_all_turns(db, session_id)
    s = orchestrator_state

    overall = compute_overall_score([r.avg_score for r in topic_score_rows])
    grade = score_to_grade(overall)
    cost = compute_cost_usd(s.haiku_input_tokens, s.haiku_output_tokens,
                            s.sonnet_input_tokens, s.sonnet_output_tokens)

    summary = {
        "overall_score": overall,
        "total_questions": len(turns),
        "topics": [
            {
                "topic_label": r.topic_label,
                "avg_score": r.avg_score,
                "grade": r.grade,
                "num_questions": r.num_questions,
            }
            for r in topic_score_rows
        ],
    }

    rendered = REPORT_GEN.format(interview_summary_json=json.dumps(summary, indent=2))
    client = get_bedrock_runtime()
    body = json.dumps({
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": 1024,
        "temperature": 0.5,
        "messages": [{"role": "user", "content": rendered}],
    })
    t0 = time.monotonic()
    response = client.invoke_model(
        modelId=settings.bedrock_sonnet_model_id, body=body,
        contentType="application/json", accept="application/json",
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    resp_body = json.loads(response["body"].read())
    text = resp_body["content"][0]["text"]
    usage = resp_body.get("usage", {})

    prev_hash = await get_last_audit_hash(db, session_id)
    await append_llm_audit(
        db=db, session_id=session_id, turn_id=-1, template_id="REPORT_GEN",
        model_id=settings.bedrock_sonnet_model_id, temperature=0.5, max_tokens=1024,
        rendered_prompt=rendered, response_text=text,
        input_tokens=usage.get("input_tokens", 0),
        output_tokens=usage.get("output_tokens", 0),
        latency_ms=latency_ms, prev_entry_hash=prev_hash,
    )
    llm_result = json.loads(text)
    return {
        "session_id": session_id,
        "overall_score": overall,
        "overall_grade": grade,
        "strengths": llm_result["strengths"],
        "gaps": llm_result["gaps"],
        "narrative": llm_result["narrative"],
        "topic_breakdown": [
            {
                "topic_id": r.topic_id,
                "topic_label": r.topic_label,
                "avg_score": r.avg_score,
                "grade": r.grade,
                "num_questions": r.num_questions,
            }
            for r in topic_score_rows
        ],
        "total_cost_usd": cost,
        "created_at": "",   # filled by save_report in DB layer
    }
```

---

## 25. `api/main.py`

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from db.database import init_db
from rag.vectorstore import warmup
from api.routes import interview, sessions, reports, audit as audit_router
from api.websocket import ws_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    warmup()         # C1: pre-load ChromaDB HNSW index before first request
    yield

app = FastAPI(title="AI Interviewer MVP", version="0.1.0", lifespan=lifespan)

app.mount("/static", StaticFiles(directory="ui/static"), name="static")
templates = Jinja2Templates(directory="ui/templates")

app.include_router(interview.router,      prefix="/interview", tags=["interview"])
app.include_router(sessions.router,       prefix="/sessions",  tags=["sessions"])
app.include_router(reports.router,        prefix="/reports",   tags=["reports"])
app.include_router(audit_router.router,   prefix="/audit",     tags=["audit"])
app.include_router(ws_router)

@app.get("/")
async def index(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/report/{session_id}")
async def report_page(request: Request, session_id: str):
    return templates.TemplateResponse("report.html", {"request": request, "session_id": session_id})
```

---

## 26. `api/routes/interview.py`

```python
import json
import uuid
from pathlib import Path
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from db.crud import create_session
from models.interview import AnswerIn, EvaluationOut
from models.session import SessionCreate
from core.orchestrator import init_session, get_next_question, submit_answer, load_session

router = APIRouter()

@router.post("/start")
async def start_interview(body: SessionCreate, db: AsyncSession = Depends(get_db)):
    q_path = Path("data/questions") / f"{body.context_name}_questions.json"
    if not q_path.exists():
        raise HTTPException(404, f"Question file not found: {q_path}")
    questions = json.loads(q_path.read_text(encoding="utf-8"))
    session_id = str(uuid.uuid4())
    await create_session(db, session_id, body.context_name, len(questions["topics"]))
    init_session(session_id, questions["topics"])
    first_q = await get_next_question(session_id, db)
    return {"session_id": session_id, "first_question": first_q}

@router.post("/answer", response_model=EvaluationOut)
async def answer_question(body: AnswerIn, db: AsyncSession = Depends(get_db)):
    s = load_session(body.session_id)
    if not s:
        raise HTTPException(404, "Session not found or expired")
    if s.state != "AWAITING_ANSWER":
        raise HTTPException(400, f"Not awaiting answer (current state: {s.state})")
    return await submit_answer(body.session_id, body.answer_text, body.answer_mode, db)

@router.get("/status/{session_id}")
async def get_status(session_id: str):
    s = load_session(session_id)
    if not s:
        raise HTTPException(404, "Session not found")
    topic = s.topics[s.current_topic_index] if s.current_topic_index < len(s.topics) else None
    return {
        "session_id": session_id,
        "state": s.state,
        "current_topic_index": s.current_topic_index,
        "total_topics": len(s.topics),
        "current_topic_label": topic.topic_label if topic else None,
        "global_turn_index": s.global_turn_index,
    }
```

---

## 27. `api/routes/reports.py`

```python
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_db
from db.models import Report
from db.crud import save_report
from core.orchestrator import load_session
from core.reporter import generate_report
from models.report import ReportOut

router = APIRouter()

@router.post("/generate/{session_id}", response_model=ReportOut)
async def generate(session_id: str, db: AsyncSession = Depends(get_db)):
    s = load_session(session_id)
    if not s or s.state != "COMPLETED":
        raise HTTPException(400, "Interview must be in COMPLETED state")
    report = await generate_report(session_id, s, db)
    saved = await save_report(db, report)
    report["created_at"] = saved.created_at
    return report

@router.get("/{session_id}", response_model=ReportOut)
async def get_report(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Report).where(Report.session_id == session_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Report not found")
    return {
        "session_id": row.session_id,
        "overall_score": row.overall_score,
        "overall_grade": row.overall_grade,
        "strengths": json.loads(row.strengths),
        "gaps": json.loads(row.gaps),
        "narrative": row.narrative,
        "topic_breakdown": json.loads(row.topic_breakdown),
        "total_cost_usd": row.total_cost_usd,
        "created_at": row.created_at,
    }
```

---

## 28. `api/routes/audit.py`

```python
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func
from db.database import get_db
from db.models import LLMAuditLog, RAGAuditLog, StateTransitionLog
from models.audit import AuditTrailOut

router = APIRouter()

@router.get("/{session_id}", response_model=AuditTrailOut)
async def get_audit_trail(session_id: str, db: AsyncSession = Depends(get_db)):
    llm_rows = (
        await db.execute(
            select(LLMAuditLog)
            .where(LLMAuditLog.session_id == session_id)
            .order_by(LLMAuditLog.id)
        )
    ).scalars().all()
    rag_count = (
        await db.execute(select(func.count()).where(RAGAuditLog.session_id == session_id))
    ).scalar()
    st_count = (
        await db.execute(select(func.count()).where(StateTransitionLog.session_id == session_id))
    ).scalar()
    return {
        "session_id": session_id,
        "total_llm_calls": len(llm_rows),
        "total_rag_retrievals": rag_count,
        "total_state_transitions": st_count,
        "llm_entries": [
            {
                "id": r.id, "session_id": r.session_id, "turn_id": r.turn_id,
                "timestamp": r.timestamp, "template_id": r.template_id,
                "model_id": r.model_id, "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens, "latency_ms": r.latency_ms,
                "entry_hash": r.entry_hash,
            }
            for r in llm_rows
        ],
    }
```

---

## 29. `api/routes/sessions.py`

```python
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from db.database import get_db
from db.models import InterviewSession
from models.session import SessionOut

router = APIRouter()

@router.get("/{session_id}", response_model=SessionOut)
async def get_session(session_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(InterviewSession).where(InterviewSession.id == session_id))
    row = result.scalar_one_or_none()
    if not row:
        raise HTTPException(404, "Session not found")
    return {
        "id": row.id, "state": row.state, "context_name": row.context_name,
        "total_topics": row.total_topics, "completed_topics": row.completed_topics,
        "overall_score": row.overall_score, "overall_grade": row.overall_grade,
        "estimated_cost_usd": row.estimated_cost_usd,
        "created_at": row.created_at, "updated_at": row.updated_at,
    }
```

---

## 30. `api/websocket.py`

```python
"""
Audio flow:
  1. Browser opens WS ws://host/ws/audio/{session_id}
  2. MediaRecorder sends PCM audio as binary chunks (16 kHz, mono, 250 ms intervals)
  3. Server streams chunks to AWS Transcribe Streaming
  4. Partial transcripts → {type: "partial", text: "..."} → browser (live captions)
  5. Final transcripts → {type: "final", text: "..."} → appended to text area
  6. 2-second silence timeout (C2: stop billing dead air) ends stream
  7. Accumulated final transcript → submit_answer() → {type: "answer_result", data: {...}}

Prerequisites: pip install amazon-transcribe
"""
import asyncio
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from amazon_transcribe.client import TranscribeStreamingClient
from amazon_transcribe.handlers import TranscriptResultStreamHandler
from amazon_transcribe.model import TranscriptEvent
from config.settings import settings

ws_router = APIRouter()

class _Handler(TranscriptResultStreamHandler):
    def __init__(self, stream, send_cb):
        super().__init__(stream)
        self._send = send_cb
        self.transcript = ""

    async def handle_transcript_event(self, event: TranscriptEvent):
        for result in event.transcript.results:
            alt_text = result.alternatives[0].transcript
            if result.is_partial:
                await self._send({"type": "partial", "text": alt_text})
            else:
                self.transcript += alt_text + " "
                await self._send({"type": "final", "text": alt_text})

@ws_router.websocket("/ws/audio/{session_id}")
async def audio_ws(websocket: WebSocket, session_id: str):
    await websocket.accept()

    client = TranscribeStreamingClient(region=settings.aws_default_region)
    stream = await client.start_stream_transcription(
        language_code="en-US",
        media_sample_rate_hz=16000,
        media_encoding="pcm",
    )

    async def send(payload: dict):
        await websocket.send_text(json.dumps(payload))

    handler = _Handler(stream.output_stream, send)
    asyncio.create_task(handler.handle_events())

    try:
        while True:
            chunk = await asyncio.wait_for(
                websocket.receive_bytes(),
                timeout=settings.audio_silence_timeout_sec,   # C2: stop stream on silence
            )
            await stream.input_stream.send_audio_event(audio_chunk=chunk)
    except (asyncio.TimeoutError, WebSocketDisconnect):
        await stream.input_stream.end_stream()

    final_text = handler.transcript.strip()
    if final_text:
        from db.database import AsyncSessionLocal
        from core.orchestrator import submit_answer
        async with AsyncSessionLocal() as db:
            result = await submit_answer(session_id, final_text, "AUDIO", db)
        await websocket.send_text(json.dumps({"type": "answer_result", "data": result}))

    await websocket.close()
```

---

## 31. `ui/templates/index.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>AI Interviewer</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div id="app">
    <header>
      <h1>AI Interviewer</h1>
      <div id="progress-container">
        <div id="progress-bar"><div id="progress-fill"></div></div>
        <span id="progress-label">0 / 0 topics</span>
      </div>
    </header>

    <main>
      <div id="topic-badge"></div>
      <div id="stretch-badge"></div>

      <section id="question-section">
        <p id="question-text">Press <strong>Start Interview</strong> to begin.</p>
      </section>

      <section id="answer-section" hidden>
        <textarea id="text-answer" rows="6" placeholder="Type your answer here..."></textarea>
        <div id="audio-row">
          <button id="mic-btn" class="btn-secondary">🎙 Hold to Speak</button>
          <span id="live-transcript"></span>
        </div>
        <button id="submit-btn" class="btn-primary">Submit Answer</button>
      </section>

      <section id="feedback-section" hidden>
        <div id="score-bar-wrapper">
          <span>Confidence:</span>
          <div id="score-bar"><div id="score-fill"></div></div>
          <span id="score-pct">0%</span>
        </div>
        <p id="reasoning-text"></p>
      </section>
    </main>

    <footer>
      <button id="start-btn" class="btn-primary">Start Interview</button>
    </footer>
  </div>
  <script>
    // Context name must match stem of seed_questions.json
    window.CONTEXT_NAME = "my_context";
  </script>
  <script src="/static/app.js"></script>
</body>
</html>
```

---

## 32. `ui/static/app.js`

```javascript
let sessionId = null;
let currentTurnIndex = 0;
let ws = null;
let mediaRecorder = null;

const $ = id => document.getElementById(id);

async function startInterview() {
  $("start-btn").disabled = true;
  const res = await fetch("/interview/start", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ context_name: window.CONTEXT_NAME }),
  });
  if (!res.ok) { alert("Failed to start interview"); return; }
  const data = await res.json();
  sessionId = data.session_id;
  $("answer-section").hidden = false;
  $("start-btn").hidden = true;
  displayQuestion(data.first_question);
  updateProgress(0, data.first_question.total_topics || 0);
}

function displayQuestion(q) {
  $("question-text").textContent = q.question_text;
  $("topic-badge").textContent = `Topic: ${q.topic_id}`;
  $("stretch-badge").textContent = q.question_type === "FOLLOW_UP"
    ? `Follow-up #${q.stretch_index}`
    : "Main Question";
  currentTurnIndex = q.turn_index;
  $("feedback-section").hidden = true;
  $("text-answer").value = "";
  $("live-transcript").textContent = "";
}

function updateProgress(done, total) {
  const pct = total > 0 ? (done / total) * 100 : 0;
  $("progress-fill").style.width = pct + "%";
  $("progress-label").textContent = `${done} / ${total} topics`;
}

async function submitTextAnswer() {
  const answer = $("text-answer").value.trim();
  if (!answer) return;
  $("submit-btn").disabled = true;
  const res = await fetch("/interview/answer", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      session_id: sessionId,
      turn_index: currentTurnIndex,
      answer_text: answer,
      answer_mode: "TEXT",
    }),
  });
  const data = await res.json();
  handleEvalResult(data);
  $("submit-btn").disabled = false;
}

function handleEvalResult(data) {
  const pct = Math.round(data.confidence_score * 100);
  $("score-pct").textContent = pct + "%";
  $("score-fill").style.width = pct + "%";
  $("score-fill").style.background = pct >= 80 ? "#22c55e" : pct >= 40 ? "#f59e0b" : "#ef4444";
  $("reasoning-text").textContent = data.reasoning;
  $("feedback-section").hidden = false;

  if (data.next_action === "COMPLETED") {
    $("answer-section").hidden = true;
    setTimeout(() => { window.location.href = `/report/${sessionId}`; }, 2000);
  } else if (data.next_question) {
    setTimeout(() => displayQuestion(data.next_question), 1500);
  }
}

function startAudioCapture() {
  if (!sessionId) return;
  ws = new WebSocket(`ws://${location.host}/ws/audio/${sessionId}`);
  ws.onmessage = e => {
    const msg = JSON.parse(e.data);
    if (msg.type === "partial") {
      $("live-transcript").textContent = msg.text;
    } else if (msg.type === "final") {
      $("text-answer").value += msg.text + " ";
      $("live-transcript").textContent = "";
    } else if (msg.type === "answer_result") {
      handleEvalResult(msg.data);
    }
  };
  navigator.mediaDevices.getUserMedia({ audio: true }).then(stream => {
    // 250 ms chunks; PCM preferred but browser may send webm — Transcribe handles both
    mediaRecorder = new MediaRecorder(stream);
    mediaRecorder.ondataavailable = e => { if (ws.readyState === 1) ws.send(e.data); };
    mediaRecorder.start(250);
  });
}

function stopAudioCapture() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") mediaRecorder.stop();
  // WS timeout on server ends the stream and triggers evaluation
}

$("start-btn").addEventListener("click", startInterview);
$("submit-btn").addEventListener("click", submitTextAnswer);
$("mic-btn").addEventListener("mousedown", startAudioCapture);
$("mic-btn").addEventListener("mouseup", stopAudioCapture);
$("mic-btn").addEventListener("touchstart", startAudioCapture);
$("mic-btn").addEventListener("touchend", stopAudioCapture);
```

---

## 33. `ui/templates/report.html`

```html
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Interview Report</title>
  <link rel="stylesheet" href="/static/style.css">
</head>
<body>
  <div id="app">
    <h1>Interview Report</h1>
    <div id="overall-card">
      <span id="overall-grade"></span>
      <span id="overall-score"></span>
      <span id="total-cost"></span>
    </div>
    <section id="narrative-section"><h2>Assessment</h2><p id="narrative"></p></section>
    <section id="strengths-section"><h2>Strengths</h2><ul id="strengths-list"></ul></section>
    <section id="gaps-section"><h2>Areas for Improvement</h2><ul id="gaps-list"></ul></section>
    <section id="topics-section"><h2>Topic Breakdown</h2><div id="topics-grid"></div></section>
  </div>
  <script>
    const sessionId = "{{ session_id }}";
    async function loadReport() {
      // Trigger generation if not done yet
      await fetch(`/reports/generate/${sessionId}`, { method: "POST" }).catch(() => {});
      const res = await fetch(`/reports/${sessionId}`);
      const r = await res.json();
      document.getElementById("overall-grade").textContent = `Grade: ${r.overall_grade}`;
      document.getElementById("overall-score").textContent = `Score: ${Math.round(r.overall_score * 100)}%`;
      document.getElementById("total-cost").textContent = `Est. cost: $${r.total_cost_usd}`;
      document.getElementById("narrative").textContent = r.narrative;
      document.getElementById("strengths-list").innerHTML = r.strengths.map(s => `<li>${s}</li>`).join("");
      document.getElementById("gaps-list").innerHTML = r.gaps.map(g => `<li>${g}</li>`).join("");
      document.getElementById("topics-grid").innerHTML = r.topic_breakdown.map(t =>
        `<div class="topic-card">
          <strong>${t.topic_label}</strong>
          <span>${Math.round(t.avg_score * 100)}% (${t.grade})</span>
          <small>${t.num_questions} question(s)</small>
        </div>`
      ).join("");
    }
    loadReport();
  </script>
</body>
</html>
```

---

## 34. IMPLEMENTATION ORDER (strict dependency graph)

```
Step 1  │ requirements.txt  .env.example  directory scaffold + all __init__.py
Step 2  │ config/settings.py  config/aws.py
Step 3  │ db/models.py  db/database.py
Step 4  │ db/crud.py                          ← depends on Step 3
Step 5  │ models/session.py  models/interview.py  models/report.py  models/audit.py
Step 6  │ rag/chunker.py  rag/embeddings.py   ← depends on Step 2
Step 7  │ rag/vectorstore.py  rag/retriever.py ← depends on Step 6
Step 8  │ scripts/ingest.py                   ← depends on Steps 6, 7
Step 9  │ core/prompts.py                     ← no deps (pure strings)
Step 10 │ core/scorer.py                      ← no deps
Step 11 │ core/evaluator.py                   ← depends on Steps 2, 9
Step 12 │ core/follow_up.py                   ← depends on Steps 2, 9
Step 13 │ core/orchestrator.py                ← depends on Steps 4, 7, 11, 12
Step 14 │ core/reporter.py                    ← depends on Steps 2, 9, 13
Step 15 │ api/routes/sessions.py  api/routes/audit.py ← depends on Steps 4, 5
Step 16 │ api/routes/reports.py               ← depends on Steps 14, 15
Step 17 │ api/routes/interview.py             ← depends on Steps 4, 13
Step 18 │ api/websocket.py                    ← depends on Step 13
Step 19 │ api/main.py                         ← depends on Steps 7, 15–18
Step 20 │ ui/static/app.js  ui/static/style.css  ui/templates/*.html
Step 21 │ RUN VERIFICATION CHECKLIST
```

Steps within a number are independent and can be created in parallel.

---

## 35. VERIFICATION CHECKLIST

Run after completing each phase. All must pass before proceeding.

### After Steps 1–2
```bash
python -c "from config.settings import settings; print(settings.top_k)"
# Expected: 5
```

### After Steps 3–4
```bash
python -c "import asyncio; from db.database import init_db; asyncio.run(init_db())"
# Expected: interview.db created with 7 tables
python -c "
import sqlite3; conn = sqlite3.connect('interview.db')
print([r[0] for r in conn.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()])
"
# Expected: ['interview_sessions','turns','topic_scores','reports','llm_audit_log','rag_audit_log','state_transition_log']
```

### After Steps 6–8
```bash
python -m scripts.ingest --context data/context/sample.txt
# Expected: "X new chunks inserted"
python -m scripts.ingest --context data/context/sample.txt
# Expected: "0 new chunks inserted (already cached)"
```

### After Steps 9–10
```bash
python -c "
from core.scorer import score_to_grade, compute_topic_score
assert score_to_grade(0.85) == 'A'
assert score_to_grade(0.70) == 'B'
assert score_to_grade(0.50) == 'C'
assert score_to_grade(0.30) == 'D'
assert score_to_grade(0.10) == 'F'
assert compute_topic_score([0.6, 0.8]) == 0.7
print('scorer OK')
"
python -c "
from core.follow_up import should_follow_up
assert should_follow_up(0.6, 1) == 'FOLLOW_UP'
assert should_follow_up(0.6, 3) == 'NEXT_TOPIC'
assert should_follow_up(0.9, 1) == 'NEXT_TOPIC'
assert should_follow_up(0.2, 1) == 'NEXT_TOPIC'
print('follow_up logic OK')
"
```

### After Steps 15–19
```bash
uvicorn api.main:app --reload --port 8000
# Expected: starts without error, ChromaDB warmup message
curl http://localhost:8000/docs
# Expected: OpenAPI UI showing all routes
```

### End-to-End (Step 21)
```
1. POST /interview/start with {"context_name": "my_context"}
   → returns session_id + first_question

2. POST /interview/answer with text answer
   → returns confidence_score + next_action

3. Repeat until next_action == "COMPLETED"

4. POST /reports/generate/{session_id}
   → returns report with overall_grade, strengths, gaps

5. GET /audit/{session_id}
   → returns llm_entries; verify entry 2 has prev_entry_hash == entry_hash of entry 1

6. Browser: open http://localhost:8000
   → interview UI loads, start → question displayed, text answer → score shown
```

---

## 36. COST ESTIMATE PER INTERVIEW (reference)

Assumptions: 5 topics × avg 2 questions each = 10 Q&A pairs

| Call type | Model | Approx tokens | Count | Cost |
|---|---|---|---|---|
| Evaluation | Haiku | ~600 in / 100 out | 10 | ~$0.007 |
| Follow-up gen | Haiku | ~400 in / 80 out | 5 | ~$0.002 |
| Report gen | Sonnet | ~800 in / 400 out | 1 | ~$0.042 |
| Embeddings (Titan) | Titan v2 | ~200 tokens | 10 | ~$0.001 |
| Audio (Transcribe) | — | ~5 min | 1 | ~$0.020 |
| **Total** | | | | **~$0.072** |

Audio is optional. Text-only interview ≈ $0.05.
