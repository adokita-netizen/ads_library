"""Campaign schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CampaignCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None


class CampaignUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None


class CampaignAdAdd(BaseModel):
    ad_id: int
    notes: Optional[str] = None


class CampaignAdItem(BaseModel):
    id: int
    ad_id: int
    notes: Optional[str] = None
    created_at: datetime
    # Ad fields
    title: Optional[str] = None
    platform: Optional[str] = None
    creative_type: Optional[str] = None
    advertiser_name: Optional[str] = None
    brand_name: Optional[str] = None
    duration_seconds: Optional[float] = None
    view_count: Optional[int] = None
    # Media URLs (presigned)
    image_url: Optional[str] = None
    video_url: Optional[str] = None
    thumbnail_url: Optional[str] = None
    snapshot_url: Optional[str] = None

    model_config = {"from_attributes": True}


class CampaignResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    user_id: int
    ad_count: int = 0
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignDetailResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    user_id: int
    ads: list[CampaignAdItem] = []
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class CampaignListResponse(BaseModel):
    campaigns: list[CampaignResponse]
    total: int
