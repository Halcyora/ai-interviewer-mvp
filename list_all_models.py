#!/usr/bin/env python
import boto3
from config.settings import settings

bedrock_client = boto3.client('bedrock', region_name=settings.aws_default_region)

try:
    response = bedrock_client.list_foundation_models()
    
    print('All available models:\n')
    for m in response.get('modelSummaries', []):
        model_id = m.get('modelId')
        provider = m.get('providerName', 'Unknown')
        model_name = m.get('modelName', '')
        print(f'{model_id}')
        print(f'  Provider: {provider} | Name: {model_name}')
        print()
        
except Exception as e:
    print(f'Error: {e}')
