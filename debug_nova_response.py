#!/usr/bin/env python
import asyncio
import json
import sys

if 'config.settings' in sys.modules:
    del sys.modules['config.settings']

from config.settings import settings
from config.aws import get_bedrock_runtime

async def test():
    client = get_bedrock_runtime()
    
    print(f'Testing Nova Pro: {settings.bedrock_nova_pro_model_id}')
    print()
    
    body = json.dumps({
        "messages": [{"role": "user", "content": [{"text": "Say hello."}]}],
        "inferenceConfig": {
            "maxTokens": 100,
            "temperature": 0.3,
        }
    })
    
    try:
        response = client.invoke_model(
            modelId=settings.bedrock_nova_pro_model_id,
            body=body,
            contentType="application/json",
            accept="application/json",
        )
        resp_body = json.loads(response["body"].read())
        
        print('[SUCCESS] Got response!')
        print('Response structure:')
        print(json.dumps(resp_body, indent=2)[:500])
        
    except Exception as e:
        print(f'[ERROR] {str(e)[:400]}')

asyncio.run(test())
