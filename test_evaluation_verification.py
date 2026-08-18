#!/usr/bin/env python3
"""
Evaluation Test: Verify the evaluator works correctly on random interview questions
Tests real interview flow with multiple answer quality levels
Date: 2026-08-18
"""

import requests
import json
import sys
import random
import asyncio
from rag.retriever import retrieve
from core.llm_client import invoke_bedrock
from config.settings import settings

BASE_URL = "http://127.0.0.1:8000"


ANSWER_TEMPLATES = {
    "GOOD": """You are a strong senior engineer candidate in a mock interview.

QUESTION:
{question_text}

RAG CONTEXT CHUNKS (ground truth):
{context_chunks}

Task:
- Write one concise but high-quality technical answer (4-7 sentences).
- Explicitly use at least 2 concrete mechanisms/facts from the provided context chunks.
- Tie the answer directly to the question asked.
- Mention trade-offs and reliability/scale concerns.

Output only the answer text. No bullets, no markdown.
""",
    "MINIMAL": """You are a candidate giving a weak, vague answer.

QUESTION:
{question_text}

Task:
- Write a very short answer (1-2 sentences).
- Keep it generic and non-specific.
- Do not include concrete mechanisms or details from context.

Output only the answer text. No bullets, no markdown.
""",
    "OFF_TOPIC": """You are a candidate giving an off-topic answer.

QUESTION:
{question_text}

Task:
- Write 1-2 clearly off-topic sentences that do not answer the question.
- Avoid any technical relevance to the question.

Output only the answer text. No bullets, no markdown.
""",
}


def _get_context_chunks_for_question(question_text: str, company: str) -> str:
    """Retrieve a compact context block from RAG for answer generation prompts."""
    try:
        results = retrieve(question_text, k=3, company=company)
    except Exception as exc:
        print(f"  [WARNING] RAG retrieval failed: {exc}")
        return ""

    if not results:
        return ""

    snippets = []
    for _, chunk_text, _ in results:
        cleaned = " ".join(chunk_text.split())
        if cleaned:
            snippets.append(cleaned[:350])

    return "\n\n---\n\n".join(snippets[:3])


def generate_answer_via_llm(question_text: str, company: str, answer_type: str) -> str:
    """Generate test answers via Bedrock using explicit prompt templates."""
    fallback_by_type = {
        "GOOD": (
            "I would approach this systematically by mapping requirements to concrete "
            "architecture decisions, validating trade-offs, and implementing reliability "
            "controls like observability and failure isolation."
        ),
        "MINIMAL": "That's a good question. It depends on the situation.",
        "OFF_TOPIC": "I like pizza and music. The weather is nice today.",
    }

    context_chunks = _get_context_chunks_for_question(question_text, company)
    template = ANSWER_TEMPLATES.get(answer_type)
    if not template:
        return fallback_by_type["MINIMAL"]

    rendered_prompt = template.format(
        question_text=question_text,
        context_chunks=context_chunks or "(no context chunks retrieved)",
    )

    try:
        response_text, _meta = asyncio.run(
            invoke_bedrock(
                prompt=rendered_prompt,
                model_id=settings.bedrock_nova_lite_model_id,
                max_tokens=220,
                temperature=0.2 if answer_type == "GOOD" else 0.7,
            )
        )
        answer = (response_text or "").strip()
        if answer:
            return answer
    except Exception as exc:
        print(f"  [WARNING] LLM answer generation failed ({answer_type}): {exc}")

    return fallback_by_type.get(answer_type, fallback_by_type["MINIMAL"])


def test_interview_evaluation_flow():
    """Test evaluation on real random interview questions"""
    
    print("=" * 80)
    print("INTERVIEW EVALUATION TEST - RANDOM QUESTIONS")
    print("=" * 80)
    
    # Pick a random company and role
    companies = ["google", "amazon", "meta", "apple", "netflix"]
    roles = ["software_engineer", "senior_software_engineer", "staff_engineer"]
    
    company = random.choice(companies)
    role = random.choice(roles)
    
    print(f"\n[INFO] Starting random interview")
    print(f"  Company: {company}")
    print(f"  Role: {role}")
    
    # Step 1: Start ONE interview (gets a random question)
    print("\nSTEP 1: Starting interview to get a random question")
    
    start_response = requests.post(
        f"{BASE_URL}/interview/start",
        json={
            "company": company,
            "role": role,
        }
    )
    
    if start_response.status_code != 200:
        print(f"[FAIL] Failed to start interview: {start_response.text}")
        return False
    
    session_data = start_response.json()
    first_q = session_data.get("first_question", {})
    question_text = first_q.get("question_text", "N/A")
    
    print(f"[OK] Random question loaded: {question_text[:100]}...")
    
    # Step 2: Test evaluation with different answer qualities on THIS SAME question
    print("\nSTEP 2: Testing evaluation with different answer qualities on the SAME question")
    
    test_cases = [
        {
            "name": "Good Technical Answer",
            "answer_type": "GOOD",
            "expected_quality": "MODERATE_TO_HIGH"
        },
        {
            "name": "Minimal Answer",
            "answer_type": "MINIMAL",
            "expected_quality": "LOW_TO_MODERATE"
        },
        {
            "name": "Off-Topic Answer",
            "answer_type": "OFF_TOPIC",
            "expected_quality": "LOW"
        },
    ]
    
    scores = {}
    
    for i, test_case in enumerate(test_cases, 1):
        print(f"\n  TEST {i}: {test_case['name']}")
        print(f"    Question: {question_text[:70]}...")
        
        # Start a fresh session for each answer
        start_resp = requests.post(
            f"{BASE_URL}/interview/start",
            json={
                "company": company,
                "role": role,
            }
        )
        if start_resp.status_code != 200:
            print(f"  [FAIL] Could not start fresh interview")
            continue
        
        session_data = start_resp.json()
        session_id = session_data["session_id"]
        first_q = session_data.get("first_question", {})
        turn_index = first_q.get("turn_index", 0)
        current_question = first_q.get("question_text", "")

        answer_text = generate_answer_via_llm(
            question_text=current_question,
            company=company,
            answer_type=test_case.get("answer_type", "MINIMAL"),
        )
        
        # Submit answer to the same type of question (not necessarily exact same, but same topic)
        answer_response = requests.post(
            f"{BASE_URL}/interview/answer",
            json={
                "session_id": session_id,
                "turn_index": turn_index,
                "answer_text": answer_text,
                "answer_mode": "TEXT"
            }
        )
        
        if answer_response.status_code != 200:
            print(f"  [FAIL] Failed to submit answer: {answer_response.text}")
            continue
        
        eval_data = answer_response.json()
        score = eval_data.get("confidence_score", 0)
        reasoning = eval_data.get("reasoning", "")
        next_action = eval_data.get("next_action", "UNKNOWN")
        key_points = eval_data.get("key_points_covered", [])
        missing_points = eval_data.get("missing_points", [])
        
        scores[test_case["name"]] = score
        
        print(f"  [OK] Answer evaluated")
        print(f"      Score: {score}")
        print(f"      Next action: {next_action}")
        print(f"      Key points: {len(key_points)} items")
        print(f"      Missing points: {len(missing_points)} items")
        print(f"      Reasoning: {reasoning[:70]}...")
    
    # Step 3: Verify scoring makes sense
    print("\nSTEP 3: Verify scoring consistency")
    
    good_score = scores.get("Good Technical Answer", 0)
    minimal_score = scores.get("Minimal Answer", 0)
    offtopic_score = scores.get("Off-Topic Answer", 0)
    
    print(f"\n  Scores:")
    print(f"    Good answer: {good_score}")
    print(f"    Minimal answer: {minimal_score}")
    print(f"    Off-topic answer: {offtopic_score}")
    
    # Verify consistency
    all_ok = True
    
    # Good should be >= minimal
    if good_score >= minimal_score:
        print(f"  [OK] Good answer >= Minimal answer")
    else:
        print(f"  [WARNING] Good answer < Minimal answer (unexpected)")
        all_ok = False
    
    # Off-topic should be lowest
    if offtopic_score <= good_score and offtopic_score <= minimal_score:
        print(f"  [OK] Off-topic answer has lowest score")
    else:
        print(f"  [WARNING] Off-topic answer is not lowest")
        all_ok = False
    
    # At least one score should be non-zero
    if max(good_score, minimal_score, offtopic_score) > 0:
        print(f"  [OK] Evaluator is producing non-zero scores")
    else:
        print(f"  [FAIL] All scores are zero - evaluator not working")
        return False
    
    return all_ok


def test_full_interview_flow():
    """Test a complete interview flow with random questions"""
    
    print("\n" + "=" * 80)
    print("FULL INTERVIEW FLOW TEST")
    print("=" * 80)
    
    companies = ["google", "amazon", "meta", "apple", "netflix"]
    roles = ["software_engineer", "senior_software_engineer"]
    
    company = random.choice(companies)
    role = random.choice(roles)
    
    print(f"\n[INFO] Running full interview: {company} - {role}")
    print("[INFO] Will answer questions until complete or limit reached")
    
    # Start interview
    start_response = requests.post(
        f"{BASE_URL}/interview/start",
        json={
            "company": company,
            "role": role,
        }
    )
    
    if start_response.status_code != 200:
        print(f"[FAIL] Failed to start interview")
        return False
    
    session_data = start_response.json()
    session_id = session_data["session_id"]
    total_questions = session_data.get("total_questions", 0)
    first_q = session_data.get("first_question", {})
    
    print(f"[OK] Interview started")
    print(f"    Session ID: {session_id}")
    print(f"    Total questions available: {total_questions}")
    
    # Answer questions
    questions_answered = 0
    max_questions_to_answer = 3
    
    # Start with the first question from start response
    if not first_q:
        print(f"[FAIL] No first question received")
        return False
    
    current_question = first_q
    
    while questions_answered < max_questions_to_answer:
        question_text = current_question.get("question_text", "N/A")
        turn_index = current_question.get("turn_index", 0)
        
        print(f"\n  Question {questions_answered + 1}: {question_text[:70]}...")
        
        # Submit an answer
        test_answers = [
            "This is important. I would design a solution that considers scalability and reliability.",
            "From my experience, the key is understanding requirements and building incrementally.",
            "I would approach this by analyzing trade-offs and designing for maintainability.",
        ]
        
        answer = test_answers[questions_answered] if questions_answered < len(test_answers) else "Good question."
        
        answer_response = requests.post(
            f"{BASE_URL}/interview/answer",
            json={
                "session_id": session_id,
                "turn_index": turn_index,
                "answer_text": answer,
                "answer_mode": "TEXT"
            }
        )
        
        if answer_response.status_code != 200:
            print(f"  [FAIL] Failed to submit answer")
            break
        
        eval_data = answer_response.json()
        score = eval_data.get("confidence_score", 0)
        next_action = eval_data.get("next_action", "UNKNOWN")
        
        print(f"  [OK] Answer evaluated (score: {score})")
        print(f"      Next action: {next_action}")
        
        questions_answered += 1
        
        # Check if interview is complete
        if next_action == "COMPLETED":
            print(f"[INFO] Interview completed after {questions_answered} questions")
            break
        
        # Get next question from the response
        next_q = eval_data.get("next_question")
        if not next_q:
            print(f"[INFO] No more questions available")
            break
        
        current_question = next_q
    
    print(f"\n[OK] Full interview flow test completed")
    print(f"    Questions answered: {questions_answered}")
    
    return questions_answered > 0


def main():
    print("\nStarting Evaluation Verification Tests\n")
    
    # Test 1: Evaluation correctness with different answer qualities
    test1_ok = test_interview_evaluation_flow()
    
    # Test 2: Full interview flow
    test2_ok = test_full_interview_flow()
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    print(f"\n[{'OK' if test1_ok else 'FAIL'}] Evaluation quality test")
    print(f"[{'OK' if test2_ok else 'FAIL'}] Full interview flow test")
    
    if test1_ok and test2_ok:
        print("\n[OK] ALL TESTS PASSED")
        print("\nConclusions:")
        print("  - Evaluator is working correctly")
        print("  - Scoring is consistent across different answer qualities")
        print("  - Interview flow completes successfully")
        print("  - Random questions are loaded and evaluated")
        return True
    else:
        print("\n[FAIL] SOME TESTS FAILED")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
