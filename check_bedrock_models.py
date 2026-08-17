#!/usr/bin/env python
import boto3
from config.settings import settings

try:
    bedrock_client = boto3.client('bedrock', region_name=settings.aws_default_region)
    
    try:
        response = bedrock_client.list_foundation_models()
        model_count = len(response.get('modelSummaries', []))
        print(f'[OK] Found {model_count} models in Bedrock')
        
        # Filter for Claude models
        claude_models = [m for m in response.get('modelSummaries', []) 
                        if 'claude' in m.get('modelId', '').lower()]
        
        print(f'[OK] Claude models available: {len(claude_models)}')
        
        print('\n[RECOMMENDED MODELS]')
        for m in claude_models:
            model_id = m.get('modelId')
            # Look for older Claude 3 models (not 3.5 or 4) that support on-demand
            if 'claude-3' in model_id and '3-5' not in model_id and '4' not in model_id:
                print(f'  {model_id}')
                
    except Exception as e:
        print(f'[ERROR] Cannot list models: {str(e)[:200]}')
        
except Exception as e:
    print(f'[ERROR] AWS connection failed: {str(e)[:200]}')
