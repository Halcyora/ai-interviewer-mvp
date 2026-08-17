#!/usr/bin/env python
import asyncio
from core.llm_client import invoke_bedrock

# Test various providers - finding one that works on-demand
MODELS_TO_TEST = [
    "mistral.voxtral-mini-3b-2507",
    "qwen.qwen3-next-80b-a3b",
    "deepseek.v3.2",
    "zai.glm-4.7-flash",
    "nvidia.nemotron-nano-12b-v2",
]

async def test_model(model_id):
    try:
        response_text, meta = await invoke_bedrock(
            model_id=model_id,
            prompt='Say hello.',
            temperature=0.3,
            max_tokens=50
        )
        print(f'[OK] {model_id}')
        return True
    except Exception as e:
        error = str(e)[:80]
        print(f'[FAIL] {model_id}')
        print(f'       {error}')
        return False

async def main():
    print('Testing available models for on-demand access...\n')
    
    for model_id in MODELS_TO_TEST:
        await test_model(model_id)
        print()

asyncio.run(main())
