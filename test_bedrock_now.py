#!/usr/bin/env python
import asyncio
import sys

if 'config.settings' in sys.modules:
    del sys.modules['config.settings']
if 'core.llm_client' in sys.modules:
    del sys.modules['core.llm_client']

from core.llm_client import invoke_bedrock
from config.settings import settings

async def test():
    print(f'Testing Bedrock Model: {settings.bedrock_nova_pro_model_id}')
    print()
    
    try:
        response_text, meta = await invoke_bedrock(
            model_id=settings.bedrock_nova_pro_model_id,
            prompt='Say hello in one sentence.',
            temperature=0.3,
            max_tokens=100
        )
        print('[SUCCESS] Bedrock is accessible!')
        print(f'Response: {response_text}')
        print(f'Tokens - Input: {meta["input_tokens"]}, Output: {meta["output_tokens"]}')
        print(f'Latency: {meta["latency_ms"]}ms')
        return True
    except Exception as e:
        error = str(e)[:400]
        print(f'[FAILED] {error}')
        return False

asyncio.run(test())
