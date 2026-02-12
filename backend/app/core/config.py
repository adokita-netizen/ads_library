"""Application configuration using pydantic-settings."""

from functools import lru_cache
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "VideoAdAnalysisPlatform"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-this-to-a-secure-random-string"
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://vaap:vaap_password@localhost:5432/vaap_db"
    database_url_sync: str = "postgresql://vaap:vaap_password@localhost:5432/vaap_db"

    # Redis
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # MinIO / S3
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_name: str = "vaap-storage"
    minio_use_ssl: bool = False

    # AI API Keys
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-5-20250929"

    # Ad Platform API Keys
    meta_access_token: Optional[str] = None
    tiktok_access_token: Optional[str] = None
    youtube_api_key: Optional[str] = None
    x_twitter_bearer_token: Optional[str] = None
    line_api_access_token: Optional[str] = None
    yahoo_ads_api_key: Optional[str] = None
    yahoo_ads_api_secret: Optional[str] = None
    pinterest_access_token: Optional[str] = None
    smartnews_ads_api_key: Optional[str] = None
    google_ads_developer_token: Optional[str] = None
    google_ads_client_id: Optional[str] = None
    google_ads_client_secret: Optional[str] = None
    google_ads_refresh_token: Optional[str] = None
    gunosy_ads_api_key: Optional[str] = None

    # Whisper
    whisper_model_size: str = "base"
    whisper_device: str = "cpu"

    # YOLO
    yolo_model_path: str = "yolov8n.pt"
    yolo_confidence_threshold: float = 0.5

    # OCR
    ocr_languages: str = "ja,en"

    # Video Processing
    max_video_duration_seconds: int = 600
    frame_extraction_fps: int = 2
    max_upload_size_mb: int = 500

    # JWT Auth
    access_token_expire_minutes: int = 30
    refresh_token_expire_days: int = 7

    # CORS
    cors_origins: str = "*"

    # Monitoring
    enable_metrics: bool = True
    metrics_port: int = 9090

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",")]

    @property
    def ocr_languages_list(self) -> list[str]:
        return [lang.strip() for lang in self.ocr_languages.split(",")]

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "case_sensitive": False}


@lru_cache()
def get_settings() -> Settings:
    return Settings()
