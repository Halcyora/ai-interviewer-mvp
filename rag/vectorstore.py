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
    """Upserts only NEW chunks — never re-embeds existing (C2). Returns count inserted."""
    collection = get_collection()
    existing_ids = set(collection.get(ids=[c["chunk_id"] for c in chunks])["ids"])
    new_pairs = [
        (c, e) for c, e in zip(chunks, embeddings)
        if c["chunk_id"] not in existing_ids
    ]
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
    """Pre-load HNSW index into memory at startup (C1: zero first-query latency)."""
    col = get_collection()
    _ = col.count()
