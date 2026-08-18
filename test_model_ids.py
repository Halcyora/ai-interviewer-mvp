import boto3
import json
from config.settings import settings

client = boto3.client('bedrock-runtime', region_name=settings.aws_default_region, 
    aws_access_key_id=settings.aws_access_key_id, aws_secret_access_key=settings.aws_secret_access_key)

# Test the incorrect model ID from .env
test_id = 'amazon.nova-lite-v1:0'
print(f'Testing INCORRECT model ID: {test_id}')
try:
    response = client.invoke_model(
        modelId=test_id,
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": "hi"}]}],
            "inferenceConfig": {"maxTokens": 100, "temperature": 0.5}
        }),
        contentType='application/json',
        accept='application/json'
    )
    print('[SUCCESS]')
except Exception as e:
    print(f'[ERROR] {str(e)[:300]}')

# Test the correct model ID
test_id = 'amazon.nova-2-lite-v1:0'
print(f'\nTesting CORRECT model ID: {test_id}')
try:
    response = client.invoke_model(
        modelId=test_id,
        body=json.dumps({
            "messages": [{"role": "user", "content": [{"text": "hi"}]}],
            "inferenceConfig": {"maxTokens": 100, "temperature": 0.5}
        }),
        contentType='application/json',
        accept='application/json'
    )
    print('[SUCCESS]')
except Exception as e:
    print(f'[ERROR] {str(e)[:300]}')
