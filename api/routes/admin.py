import shutil
from pathlib import Path
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession
from db.database import get_db
from rag.chunker import load_document, chunk_text
from rag.embeddings import embed_texts
from rag.vectorstore import upsert_chunks
from core.question_generator import generate_questions_for_context

router = APIRouter()

_ALLOWED_SUFFIXES = {".pdf", ".docx", ".txt"}


@router.get("/contexts")
async def list_contexts():
    """Lists every ingested context and whether a questions file exists."""
    context_dir = Path("data/context")
    questions_dir = Path("data/questions")
    contexts = []
    for f in sorted(context_dir.iterdir()):
        if f.suffix.lower() in _ALLOWED_SUFFIXES:
            has_q = (questions_dir / f"{f.stem}_questions.json").exists()
            contexts.append({
                "context_name": f.stem,
                "filename": f.name,
                "has_questions": has_q,
            })
    return {"contexts": contexts}


@router.post("/upload")
async def upload_context(file: UploadFile = File(...)):
    """Saves uploaded file to data/context/ and immediately ingests into ChromaDB."""
    suffix = Path(file.filename).suffix.lower()
    if suffix not in _ALLOWED_SUFFIXES:
        raise HTTPException(400, f"Unsupported type '{suffix}'. Allowed: pdf, docx, txt")

    dest = Path("data/context") / file.filename
    with dest.open("wb") as buf:
        shutil.copyfileobj(file.file, buf)

    text = load_document(str(dest))
    context_name = dest.stem
    chunks = chunk_text(text, context_name)
    embeddings = embed_texts([c["text"] for c in chunks])
    inserted = upsert_chunks(chunks, embeddings)
    return {
        "context_name": context_name,
        "filename": file.filename,
        "total_chunks": len(chunks),
        "chunks_inserted": inserted,
        "chunks_cached": len(chunks) - inserted,
    }


@router.post("/generate-questions")
async def generate_questions(
    context_name: str = Form(...),
    num_topics: int = Form(5),
    db: AsyncSession = Depends(get_db),
):
    """Calls Sonnet to auto-generate questions from ChromaDB chunks for a context."""
    try:
        result = await generate_questions_for_context(context_name, num_topics, db)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return {
        "context_name": result["context_name"],
        "num_topics": len(result["topics"]),
        "topics": result["topics"],
        "saved_to": f"data/questions/{context_name}_questions.json",
    }
