"""
Generate questions for all company-role combinations using LLM.
Usage: python -m scripts.generate_questions_batch
"""
import asyncio
from db.database import AsyncSessionLocal
from core.question_generator import generate_questions_for_context

COMPANIES = ["google", "amazon", "meta", "apple", "netflix"]
ROLES = [
    "software_engineer",
    "senior_software_engineer",
    "staff_engineer",
    "engineering_manager",
    "product_manager"
]


async def main():
    # Use shared database session from db.database
    total = len(COMPANIES) * len(ROLES)
    count = 0
    
    for company in COMPANIES:
        for role in ROLES:
            count += 1
            context_name = f"{company}_{role}"
            print(f"\n[{count}/{total}] Generating questions for {context_name}...")
            
            try:
                async with AsyncSessionLocal() as db:
                    result = await generate_questions_for_context(
                        context_name=context_name,
                        num_topics=5,  # 5 topics × 12 questions per topic = 60 questions
                        db=db,
                    )
                    num_questions = len(result.get("topics", []))
                    print(f"  [OK] Generated for {context_name}")
            except Exception as e:
                print(f"  [FAIL] Error generating for {context_name}: {e}")
    
    print(f"\n[COMPLETE] Batch generation complete!")


if __name__ == "__main__":
    asyncio.run(main())
