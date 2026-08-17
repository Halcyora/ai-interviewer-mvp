from typing import List, Tuple, Optional
from rag.vectorstore import get_collection
from rag.embeddings import embed_single
from config.settings import settings


def retrieve(query: str, k: int | None = None, company: Optional[str] = None) -> List[Tuple[str, str, float]]:
    """Returns [(chunk_id, text, similarity_score)] sorted descending by score.
    
    If company is provided, filters results to only include chunks from that company's context.
    """
    k = k or settings.top_k
    collection = get_collection()
    query_vec = embed_single(query)
    
    # Build where filter for company if provided
    where_filter = None
    if company:
        where_filter = {"source": {"$eq": company}}
    
    results = collection.query(
        query_embeddings=[query_vec],
        n_results=k,
        include=["documents", "distances"],
        where=where_filter,
    )
    return [
        (cid, doc, round(1.0 - dist, 4))
        for cid, doc, dist in zip(
            results["ids"][0],
            results["documents"][0],
            results["distances"][0],
        )
    ]
