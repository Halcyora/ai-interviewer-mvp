from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    aws_access_key_id: str
    aws_secret_access_key: str
    aws_default_region: str = "us-east-1"
    bedrock_nova_lite_model_id: str = "amazon.nova-lite-v1:0"
    bedrock_nova_pro_model_id: str = "amazon.nova-pro-v1:0"
    bedrock_inference_profile_id: Optional[str] = None
    bedrock_embed_model_id: str = "amazon.titan-embed-text-v2:0"
    chroma_persist_dir: str = "./chroma_db"
    sqlite_db_path: str = "./interview.db"
    top_k: int = 5
    chunk_size: int = 512
    chunk_overlap: int = 50
    # Thresholds for follow-up decision (0.4-0.8 range triggers follow-up)
    follow_up_threshold_low: float = 0.4
    follow_up_threshold_high: float = 0.8
    # Max stretch count: 1 (seed) + 2 (follow-ups) = 3 total attempts per topic
    max_stretch_count: int = 3
    audio_silence_timeout_sec: float = 2.0
    log_level: str = "INFO"


settings = Settings()
