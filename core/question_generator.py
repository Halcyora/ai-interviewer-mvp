import json
from pathlib import Path
from config.settings import settings
from core.prompts import QUESTION_GEN
from core.llm_client import invoke_and_audit_llm
from rag.vectorstore import get_collection


async def generate_questions_for_context(
    context_name: str,
    num_topics: int,
    db,
) -> dict:
    """
    Retrieves chunks for context_name from ChromaDB, calls Sonnet to generate
    topic+question pairs, saves to data/questions/{context_name}_questions.json.
    Returns the parsed questions dict.
    """
    collection = get_collection()
    results = collection.get(
        where={"source": {"$eq": context_name}},
        include=["documents"],
    )
    docs = results.get("documents") or []
    if not docs:
        raise ValueError(
            f"No chunks found for context '{context_name}'. Run ingest first."
        )

    # Sample up to 20 chunks spread evenly across the document
    step = max(1, len(docs) // 20)
    sample_docs = docs[::step][:20]
    context_text = "\n\n---\n\n".join(sample_docs)

    rendered = QUESTION_GEN.format(
        context_text=context_text,
        num_topics=num_topics,
    )
    
    text, meta = await invoke_and_audit_llm(
        db=db,
        session_id="admin",
        turn_id=-1,
        template_id="QUESTION_GEN",
        model_id=settings.bedrock_sonnet_model_id,
        temperature=0.3,
        max_tokens=2048,
        rendered_prompt=rendered,
        prompt=rendered,
    )

    llm_result = json.loads(text)
    questions_data = {
        "context_name": context_name,
        "topics": llm_result["topics"],
    }
    out_path = Path("data/questions") / f"{context_name}_questions.json"
    out_path.write_text(json.dumps(questions_data, indent=2), encoding="utf-8")
    return questions_data
