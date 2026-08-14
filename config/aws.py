import boto3
from functools import lru_cache
from config.settings import settings


@lru_cache(maxsize=1)
def get_bedrock_runtime() -> boto3.client:
    return boto3.client(
        "bedrock-runtime",
        region_name=settings.aws_default_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )


@lru_cache(maxsize=1)
def get_transcribe_client() -> boto3.client:
    return boto3.client(
        "transcribestreaming",
        region_name=settings.aws_default_region,
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
    )
