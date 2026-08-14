import hashlib
from pathlib import Path
from typing import List
from langchain_text_splitters import RecursiveCharacterTextSplitter
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
        # deterministic ID prevents re-embedding identical content (C2)
        chunk_hash = hashlib.sha256(doc.page_content.encode()).hexdigest()[:16]
        chunks.append({
            "chunk_id": f"{source}__{i}__{chunk_hash}",
            "text": doc.page_content,
            "source": source,
            "char_start": doc.metadata.get("start_index", 0),
        })
    return chunks
