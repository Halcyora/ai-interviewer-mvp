#!/usr/bin/env python3
"""Check available Bedrock inference profiles in your account."""
import boto3
import json
from config.settings import settings

# Try to list inference profiles
try:
    client = boto3.client(
        "bedrock",
        region_name=settings.aws_default_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
    
    # List inference profiles
    response = client.list_inference_profiles()
    profiles = response.get("inferenceProfileSummaries", [])
    
    print("Available Inference Profiles:")
    print("=" * 80)
    if not profiles:
        print("No inference profiles found. You need to create one in AWS Bedrock console.")
        print("\nTo create an inference profile:")
        print("1. Go to AWS Bedrock Console")
        print("2. Select 'Inference profiles' (or 'Provisioned throughput' in some regions)")
        print("3. Create a profile that includes: amazon.nova-2-lite-v1:0")
        print("4. Copy the profile ARN and add to .env as:")
        print("   BEDROCK_TEXT_INFERENCE_PROFILE_ID=<your-profile-arn>")
    else:
        for profile in profiles:
            print(f"\nProfile Name: {profile.get('inferenceProfileName')}")
            print(f"Profile ID: {profile.get('inferenceProfileId')}")
            print(f"Status: {profile.get('status')}")
            print(f"Models: {profile.get('models', [])}")
            
except Exception as e:
    print(f"Error: {e}")
    print("\nMake sure your AWS credentials are valid in .env")
