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
