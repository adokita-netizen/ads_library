"""Ad-related Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, model_validator


class AdCreate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    platform: str
    category: Optional[str] = None
    video_url: Optional[str] = None
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
    video_url: Optional[str] = None
    s3_key: Optional[str] = None
    duration_seconds: Optional[float] = None
    advertiser_name: Optional[str] = None
    brand_name: Optional[str] = None
    estimated_ctr: Optional[float] = None
    view_count: Optional[int] = None
    tags: Optional[list[str]] = None
    destination_url: Optional[str] = None
    destination_type: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @model_validator(mode="before")
    @classmethod
    def extract_metadata_fields(cls, data):
        """Extract destination_url and destination_type from ad_metadata JSONB."""
        if hasattr(data, "__dict__"):
            metadata = getattr(data, "ad_metadata", None) or {}
            d = {k: v for k, v in data.__dict__.items() if not k.startswith("_")}
            d["destination_url"] = metadata.get("destination_url")
            d["destination_type"] = metadata.get("destination_type")
            return d
        if isinstance(data, dict):
            metadata = data.get("ad_metadata") or data.get("metadata") or {}
            if isinstance(metadata, dict):
                data.setdefault("destination_url", metadata.get("destination_url"))
                data.setdefault("destination_type", metadata.get("destination_type"))
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
