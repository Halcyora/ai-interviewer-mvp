"""
Generate questions for all company-role combinations using LLM.
Creates 60 questions per file: 20 beginner, 20 intermediate, 20 advanced.
Usage: python -m scripts.generate_questions_proper
"""
import asyncio
import json
from pathlib import Path
from db.database import AsyncSessionLocal
from core.llm_client import invoke_bedrock
from config.settings import settings
from rag.vectorstore import get_collection

COMPANIES = ["google", "amazon", "meta", "apple", "netflix"]
ROLES = [
    "software_engineer",
    "senior_software_engineer",
    "staff_engineer",
    "engineering_manager",
    "product_manager"
]


async def generate_questions_for_context_proper(
    company: str,
    role: str,
    db,
) -> dict:
    """Generate 60 questions (20 per difficulty) using LLM."""
    
    context_name = f"{company}_{role}"
    
    # Retrieve company context from ChromaDB
    collection = get_collection()
    results = collection.get(
        where={"source": {"$eq": company}},
        include=["documents"],
    )
    docs = results.get("documents") or []
    if not docs:
        raise ValueError(f"No chunks found for company '{company}'")

    # Sample up to 20 chunks
    step = max(1, len(docs) // 20)
    sample_docs = docs[::step][:20]
    context_text = "\n\n---\n\n".join(sample_docs)

    # Generate questions by difficulty level
    all_questions = []
    question_id = 1
    
    for difficulty in ["beginner", "intermediate", "advanced"]:
        prompt = f"""Based on the following context about {company.upper()}, generate 20 high-quality interview questions for a {role.replace('_', ' ')} role at the {difficulty} difficulty level.

CONTEXT:
{context_text}

Generate exactly 20 questions. For each question, provide:
- A clear, specific question relevant to {company} and the {role} role
- The question should be at {difficulty} level

Return as a JSON array with this format:
[
  {{"question": "What is...?"}},
  {{"question": "How would you...?"}}
  ...
]

Make sure to generate EXACTLY 20 questions. Return ONLY the JSON array, no other text."""

        try:
            response_text, meta = await invoke_bedrock(
                model_id=settings.bedrock_nova_pro_model_id,
                prompt=prompt,
                temperature=0.7,
                max_tokens=3000
            )
            
            # Parse the response - extract JSON array
            response_text = response_text.strip()
            if response_text.startswith("```"):
                response_text = response_text.split("```")[1]
                if response_text.startswith("json"):
                    response_text = response_text[4:]
            response_text = response_text.strip()
            
            questions_data = json.loads(response_text)
            
            for idx, q_obj in enumerate(questions_data, 1):
                q_text = q_obj.get("question", "")
                if q_text:
                    all_questions.append({
                        "id": f"q_{question_id:03d}",
                        "text": q_text,
                        "difficulty": difficulty,
                        "topic": f"{difficulty.capitalize()} Topic",
                        "company": company,
                        "role": role
                    })
                    question_id += 1
                    
        except Exception as e:
            print(f"  Error generating {difficulty} questions: {str(e)[:100]}")
            continue

    # Structure with company and role info
    result = {
        "company": company,
        "role": role,
        "questions": all_questions
    }
    
    # Save to file
    out_path = Path("data/questions") / f"{context_name}_questions.json"
    out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
    
    return result


async def main():
    total = len(COMPANIES) * len(ROLES)
    count = 0
    
    for company in COMPANIES:
        for role in ROLES:
            count += 1
            context_name = f"{company}_{role}"
            print(f"\n[{count}/{total}] Generating {context_name}...")
            
            try:
                async with AsyncSessionLocal() as db:
                    result = await generate_questions_for_context_proper(
                        company=company,
                        role=role,
                        db=db,
                    )
                    num_questions = len(result.get("questions", []))
                    print(f"  [OK] Generated {num_questions} questions")
            except Exception as e:
                print(f"  [ERROR] {str(e)[:100]}")
    
    print(f"\n[COMPLETE] Batch generation complete!")


if __name__ == "__main__":
    asyncio.run(main())
