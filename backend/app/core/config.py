"""Application configuration using pydantic-settings."""

import json
import logging
import os
from functools import lru_cache
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings

_config_logger = logging.getLogger(__name__)
_BACKEND_ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


def _normalize_database_url(url: str, driver: str = "asyncpg") -> str:
    """Normalize database URL for different providers (PostgreSQL各種プロバイダー).

    Handles:
    - postgres:// -> postgresql+asyncpg:// (or postgresql://)
    - postgresql:// -> postgresql+asyncpg:// (for async)
    - Already correct URLs pass through unchanged
    """
    if not url:
        return url
    if driver == "asyncpg":
        for prefix in ("postgres://", "postgresql://"):
            if url.startswith(prefix):
                return url.replace(prefix, "postgresql+asyncpg://", 1)
    else:
        for prefix in ("postgres://", "postgresql+asyncpg://"):
            if url.startswith(prefix):
                return url.replace(prefix, "postgresql://", 1)
    return url


_INSECURE_SECRET_KEYS = frozenset({
    "change-this-to-a-secure-random-string",
    "secret",
    "secret_key",
    "",
})


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    app_name: str = "VideoAdAnalysisPlatform"
    app_env: str = "development"
    debug: bool = True
    secret_key: str = "change-this-to-a-secure-random-string"
    api_v1_prefix: str = "/api/v1"
    api_v2_prefix: str = "/api/v2"
    api_dual_case_output: bool = True
    api_compression_enabled: bool = True
    api_compression_min_size_bytes: int = 1024
    api_compression_gzip_enabled: bool = True
    api_compression_brotli_enabled: bool = True
    api_compression_gzip_level: int = 6
    api_compression_brotli_quality: int = 5
    api_gateway_auth_enabled: bool = False
    api_gateway_api_keys: str = ""
    api_gateway_protected_prefixes: str = "/api/v2,/api/v1/graphql"
    cache_key_version: str = "v1"
    api_db_query_timeout_ms: int = 30_000

    @field_validator("secret_key")
    @classmethod
    def _validate_secret_key(cls, v):
        if v in _INSECURE_SECRET_KEYS and os.getenv("APP_ENV", "").lower() in ("production", "prod"):
            raise ValueError("SECRET_KEY must be set to a secure value in production")
        return v

    # Rate limiting
    rate_limit_login: str = "5/minute"
    rate_limit_register: str = "3/minute"
    rate_limit_rankings_read: str = "60/minute"
    rate_limit_rankings_heavy: str = "20/minute"

    @property
    def is_secret_key_secure(self) -> bool:
        return self.secret_key not in _INSECURE_SECRET_KEYS and len(self.secret_key) >= 32

    # Database — accepts DATABASE_URL in any format (postgres://, postgresql://)
    # DATABASE_URLで指定。Lambda環境ではDB_SECRET_ARN使用。
    database_url: str = "postgresql+asyncpg://vaap:vaap_password@localhost:5432/vaap_db"
    database_url_sync: str = ""

    # Secrets Manager ARN for DB password (Lambda deployments)
    db_secret_arn: str = ""
    db_username: str = ""
    db_endpoint: str = ""
    db_name: str = ""

    # Read replica URL (optional, falls back to primary if empty)
    database_read_url: str = ""
    database_read_url_sync: str = ""

    # Database pool — Lambda / コンテナ環境向け
    db_pool_size: int = 5
    db_max_overflow: int = 3

    # Redis — redis:// or rediss:// (TLS) URLs
    redis_url: str = "redis://localhost:6379/0"
    celery_broker_url: str = "redis://localhost:6379/1"
    celery_result_backend: str = "redis://localhost:6379/2"

    # Storage backend: "minio" (local dev) or "s3" (AWS)
    storage_backend: str = "minio"

    # MinIO / S3 (optional in cloud deploy)
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket_name: str = "vaap-storage"
    minio_use_ssl: bool = False

    # AWS S3 (when storage_backend="s3")
    aws_s3_bucket: str = ""
    aws_region: str = "ap-northeast-1"

    # AWS CloudFront CDN (optional, for media serving)
    aws_cloudfront_domain: str = ""
    aws_cloudfront_enabled: bool = False

    # Task backend: "celery" (local dev) or "sqs" (AWS)
    task_backend: str = "celery"
    sqs_heavy_queue_url: str = ""
    sqs_light_queue_url: str = ""

    @model_validator(mode="after")
    def _resolve_db_secret(self) -> "Settings":
        """If DB_SECRET_ARN is set, fetch password from Secrets Manager and build DATABASE_URL."""
        if self.db_secret_arn and self.db_endpoint:
            try:
                import boto3
                client = boto3.client("secretsmanager", region_name=os.environ.get("AWS_REGION", "ap-northeast-1"))
                resp = client.get_secret_value(SecretId=self.db_secret_arn)
                password = resp["SecretString"]
                self.database_url = f"postgresql+asyncpg://{self.db_username}:{password}@{self.db_endpoint}/{self.db_name}"
                self.database_url_sync = ""  # will be derived below
            except Exception as e:
                if os.getenv("APP_ENV", "").lower() in ("production", "prod"):
                    raise ValueError(f"Failed to resolve DB secret from Secrets Manager: {e}")
                _config_logger.warning("Failed to resolve DB secret from Secrets Manager: %s", e)
        return self

    @model_validator(mode="after")
    def _derive_urls(self) -> "Settings":
        """Auto-derive database_url_sync, read replica URLs, and normalize URL schemes."""
        # Normalize async URL
        self.database_url = _normalize_database_url(self.database_url, driver="asyncpg")
        # Auto-derive sync URL if not explicitly set
        if not self.database_url_sync:
            self.database_url_sync = _normalize_database_url(
                self.database_url, driver="sync"
            )
        else:
            self.database_url_sync = _normalize_database_url(
                self.database_url_sync, driver="sync"
            )
        # Read replica: normalize if set, otherwise left empty (fallback to primary)
        if self.database_read_url:
            self.database_read_url = _normalize_database_url(self.database_read_url, driver="asyncpg")
            if not self.database_read_url_sync:
                self.database_read_url_sync = _normalize_database_url(self.database_read_url, driver="sync")
            else:
                self.database_read_url_sync = _normalize_database_url(self.database_read_url_sync, driver="sync")
        return self

    # AI API Keys
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4-turbo-preview"
    anthropic_api_key: Optional[str] = None
    anthropic_model: str = "claude-sonnet-4-5-20250929"
    ai_chat_use_claude: bool = True
    ai_chat_claude_max_tokens: int = 1200
    ai_chat_claude_timeout_seconds: float = 30.0
    ai_chat_requests_per_hour: int = 60
    ai_chat_tokens_per_day: int = 120_000

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

    @property
    def api_gateway_api_keys_list(self) -> list[str]:
        return [item.strip() for item in self.api_gateway_api_keys.split(",") if item.strip()]

    @property
    def api_gateway_protected_prefixes_list(self) -> list[str]:
        return [item.strip() for item in self.api_gateway_protected_prefixes.split(",") if item.strip()]

    model_config = {
        "env_file": str(_BACKEND_ENV_FILE),
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
    }


@lru_cache()
def get_settings() -> Settings:
    return Settings()




