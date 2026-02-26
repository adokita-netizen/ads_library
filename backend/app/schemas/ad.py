"""Ad-related Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class AdCreate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    platform: str
    category: Optional[str] = None
    creative_type: Optional[str] = None
    video_url: Optional[str] = None
    image_url: Optional[str] = None
    advertiser_name: Optional[str] = None
    brand_name: Optional[str] = None
    tags: list[str] = Field(default_factory=list)


class AdResponse(BaseModel):
    id: int
    external_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    platform: str
    status: str
    category: Optional[str] = None
    creative_type: Optional[str] = None
    video_url: Optional[str] = None
    s3_key: Optional[str] = None
    thumbnail_url: Optional[str] = None
    image_url: Optional[str] = None
    image_s3_key: Optional[str] = None
    all_image_urls: Optional[list[str]] = None
    snapshot_url: Optional[str] = None
    media_extraction_status: Optional[str] = None
    duration_seconds: Optional[float] = None
    advertiser_name: Optional[str] = None
    brand_name: Optional[str] = None
    estimated_ctr: Optional[float] = None
    view_count: Optional[int] = None
    spend: Optional[float] = None
    impressions: Optional[int] = None
    reach: Optional[int] = None
    cpc: Optional[float] = None
    cpm: Optional[float] = None
    frequency: Optional[float] = None
    tags: Optional[list[str]] = None
    destination_url: Optional[str] = None
    destination_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_metadata_fields(cls, data):
        """Extract extra fields from ad_metadata JSONB and resolve thumbnail/image URLs."""
        if hasattr(data, "__dict__"):
            metadata = getattr(data, "ad_metadata", None) or {}
            d = {k: v for k, v in data.__dict__.items() if not k.startswith("_")}
            # destination_url: prefer column value, fallback to metadata
            if not d.get("destination_url"):
                d["destination_url"] = metadata.get("destination_url")
            d["destination_type"] = metadata.get("destination_type")
            # thumbnail_url: prefer column, then try to build from thumbnail_s3_key
            # (presigned URL generation happens in endpoint, here we just ensure the field is set)
            # all_image_urls: expand from image_s3_keys JSONB
            image_s3_keys = d.get("image_s3_keys")
            if isinstance(image_s3_keys, dict):
                d["all_image_urls"] = image_s3_keys.get("urls", [])
            return d
        if isinstance(data, dict):
            metadata = data.get("ad_metadata") or data.get("metadata") or {}
            if isinstance(metadata, dict):
                if not data.get("destination_url"):
                    data["destination_url"] = metadata.get("destination_url")
                data.setdefault("destination_type", metadata.get("destination_type"))
            image_s3_keys = data.get("image_s3_keys")
            if isinstance(image_s3_keys, dict):
                data["all_image_urls"] = image_s3_keys.get("urls", [])
        return data


class AdListResponse(BaseModel):
    ads: list[AdResponse]
    total: int
    page: int
    page_size: int


class AdSearchRequest(BaseModel):
    query: str
    platforms: Optional[list[str]] = None
    category: Optional[str] = None
    advertiser: Optional[str] = None
    min_duration: Optional[float] = None
    max_duration: Optional[float] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = 1
    page_size: int = 20


class AdAnalysisResponse(BaseModel):
    ad_id: int
    total_scenes: Optional[int] = None
    avg_scene_duration: Optional[float] = None
    face_closeup_ratio: Optional[float] = None
    product_display_ratio: Optional[float] = None
    text_overlay_ratio: Optional[float] = None
    is_ugc_style: Optional[bool] = None
    has_narration: Optional[bool] = None
    has_subtitles: Optional[bool] = None
    hook_type: Optional[str] = None
    hook_text: Optional[str] = None
    hook_score: Optional[float] = None
    cta_text: Optional[str] = None
    overall_sentiment: Optional[str] = None
    sentiment_score: Optional[float] = None
    full_transcript: Optional[str] = None
    keywords: Optional[list] = None
    dominant_color_palette: Optional[list] = None
    winning_score: Optional[float] = None

    model_config = {"from_attributes": True}


class CrawlRequest(BaseModel):
    query: str
    platforms: list[str] = Field(
        default=[
            "facebook", "instagram", "youtube", "tiktok",
            "yahoo", "x_twitter", "line", "pinterest",
            "smartnews", "google_ads", "gunosy",
        ]
    )
    category: Optional[str] = None
    limit_per_platform: int = Field(default=20, ge=1, le=100)
    auto_analyze: bool = False


class CrawlResponse(BaseModel):
    task_id: str
    status: str
    message: str
