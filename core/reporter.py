import json
from config.settings import settings
from core.prompts import REPORT_GEN
from core.llm_client import invoke_and_audit_llm
from core.scorer import compute_session_scores, compute_cost_usd
from db.crud import get_topic_scores, get_all_turns


async def generate_report(session_id: str, orchestrator_state, db) -> dict:
    """Uses Sonnet for quality narrative (C1). Writes audit row (C3)."""
    topic_score_rows = await get_topic_scores(db, session_id)
    turns = await get_all_turns(db, session_id)
    s = orchestrator_state

    # Compute all scores in one place
    score_data = compute_session_scores(topic_score_rows)
    overall = score_data["overall_score"]
    grade = score_data["overall_grade"]
    
    cost = compute_cost_usd(
        getattr(s, "nova_lite_input_tokens", 0),
        getattr(s, "nova_lite_output_tokens", 0),
        getattr(s, "nova_pro_input_tokens", 0),
        getattr(s, "nova_pro_output_tokens", 0),
    )

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
    
    text, meta = await invoke_and_audit_llm(
        db=db,
        session_id=session_id,
        turn_id=-1,
        template_id="REPORT_GEN",
        model_id=settings.bedrock_nova_pro_model_id,
        temperature=0.5,
        max_tokens=1024,
        rendered_prompt=rendered,
        prompt=rendered,
    )

    # Accumulate report generation tokens (Nova Pro)
    nova_pro_input_tokens = getattr(s, "nova_pro_input_tokens", 0) + meta.get("input_tokens", 0)
    nova_pro_output_tokens = getattr(s, "nova_pro_output_tokens", 0) + meta.get("output_tokens", 0)
    
    # Recompute cost with all tokens including report generation
    total_cost = compute_cost_usd(
        getattr(s, "nova_lite_input_tokens", 0),
        getattr(s, "nova_lite_output_tokens", 0),
        nova_pro_input_tokens,
        nova_pro_output_tokens,
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
        "total_cost_usd": total_cost,
        "created_at": "",  # filled by save_report in DB layer
    }
