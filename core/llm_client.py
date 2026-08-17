"""
Centralized LLM client for AWS Bedrock invocations and audit logging.
Eliminates redundant API call patterns across evaluator, question_generator, follow_up, and reporter.
"""
import json
import time
from typing import Tuple, Dict, Any
from config.settings import settings
from config.aws import get_bedrock_runtime
from db.crud import append_llm_audit, get_last_audit_hash


async def invoke_bedrock(
    prompt: str,
    model_id: str,
    max_tokens: int,
    temperature: float,
) -> Tuple[str, Dict[str, int]]:
    """
    Invokes LLM via AWS Bedrock and returns response text and usage metadata.
    Supports multiple model types: Anthropic Claude, Amazon Nova, etc.

    Args:
        prompt: The prompt to send to the model
        model_id: Bedrock model ID (e.g., settings.bedrock_nova_lite_model_id)
        max_tokens: Maximum tokens in response
        temperature: Model temperature (0.0 to 1.0)

    Returns:
        Tuple of (response_text, {input_tokens, output_tokens, latency_ms})
    """
    client = get_bedrock_runtime()
    
    # Determine request format based on model provider
    if "claude" in model_id.lower():
        # Anthropic Claude format
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        })
    elif "nova" in model_id.lower():
        # Amazon Nova format
        body = json.dumps({
            "messages": [{"role": "user", "content": [{"text": prompt}]}],
            "inferenceConfig": {
                "maxTokens": max_tokens,
                "temperature": temperature,
            }
        })
    else:
        # Default to Claude format for others
        body = json.dumps({
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "messages": [{"role": "user", "content": prompt}],
        })
    
    t0 = time.monotonic()
    response = client.invoke_model(
        modelId=model_id,
        body=body,
        contentType="application/json",
        accept="application/json",
    )
    latency_ms = int((time.monotonic() - t0) * 1000)
    
    resp_body = json.loads(response["body"].read())
    
    # Parse response based on model type
    if "claude" in model_id.lower():
        text = resp_body["content"][0]["text"]
        usage = resp_body.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
    elif "nova" in model_id.lower():
        # Amazon Nova wraps content under output.message.content
        text = resp_body["output"]["message"]["content"][0]["text"]
        usage = resp_body.get("usage", {})
        input_tokens = usage.get("inputTokens", 0)
        output_tokens = usage.get("outputTokens", 0)
    else:
        text = resp_body["content"][0]["text"]
        usage = resp_body.get("usage", {})
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
    
    return text, {
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latency_ms": latency_ms,
    }


async def invoke_and_audit_llm(
    db: Any,
    session_id: str,
    turn_id: int,
    template_id: str,
    model_id: str,
    temperature: float,
    max_tokens: int,
    rendered_prompt: str,
    prompt: str,
) -> Tuple[str, Dict[str, int]]:
    """
    Invokes Claude via Bedrock and automatically logs the call to audit trail.
    Retrieves the previous audit hash internally.

    Args:
        db: AsyncSession database connection
        session_id: Session identifier
        turn_id: Turn identifier
        template_id: Template identifier (e.g., "EVALUATOR", "FOLLOW_UP_GEN")
        model_id: Bedrock model ID
        temperature: Model temperature
        max_tokens: Maximum tokens in response
        rendered_prompt: Full rendered prompt for audit logging
        prompt: Prompt to send to the model

    Returns:
        Tuple of (response_text, {input_tokens, output_tokens, latency_ms})
    """
    # Invoke the model
    response_text, meta = await invoke_bedrock(
        prompt=prompt,
        model_id=model_id,
        max_tokens=max_tokens,
        temperature=temperature,
    )
    
    # Get previous audit hash
    prev_hash = await get_last_audit_hash(db, session_id)
    
    # Log the call
    await append_llm_audit(
        db=db,
        session_id=session_id,
        turn_id=turn_id,
        template_id=template_id,
        model_id=model_id,
        temperature=temperature,
        max_tokens=max_tokens,
        rendered_prompt=rendered_prompt,
        response_text=response_text,
        input_tokens=meta["input_tokens"],
        output_tokens=meta["output_tokens"],
        latency_ms=meta["latency_ms"],
        prev_entry_hash=prev_hash,
    )
    
    return response_text, meta
