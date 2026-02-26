"""Pydantic schemas for Meta campaign management operations."""

from typing import Optional

from pydantic import BaseModel, Field


class CreateCampaignRequest(BaseModel):
    """Create a new Meta campaign."""
    account_id: str
    name: str = Field(..., min_length=1, max_length=400)
    objective: str = Field(..., description="Campaign objective: OUTCOME_TRAFFIC, OUTCOME_SALES, etc.")
    daily_budget: Optional[int] = Field(None, ge=100, description="Daily budget in cents (e.g., 100000 = ¥1,000)")
    lifetime_budget: Optional[int] = Field(None, ge=100, description="Lifetime budget in cents")
    special_ad_categories: list[str] = []


class UpdateCampaignStatusRequest(BaseModel):
    """Update campaign status."""
    status: str = Field(..., pattern="^(ACTIVE|PAUSED|DELETED|ARCHIVED)$")


class CreateAdSetRequest(BaseModel):
    """Create a new Meta ad set."""
    account_id: str
    campaign_id: str
    name: str = Field(..., min_length=1, max_length=400)
    daily_budget: Optional[int] = Field(None, ge=100)
    lifetime_budget: Optional[int] = None
    optimization_goal: str = "LINK_CLICKS"
    billing_event: str = "IMPRESSIONS"
    bid_strategy: Optional[str] = None
    bid_amount: Optional[int] = None
    targeting: Optional[dict] = None
    start_time: Optional[str] = None
    end_time: Optional[str] = None


class CreateAdRequest(BaseModel):
    """Create a new Meta ad."""
    account_id: str
    ad_set_id: str
    name: str = Field(..., min_length=1, max_length=400)
    creative_id: str


class CreateCreativeRequest(BaseModel):
    """Create a new ad creative."""
    account_id: str
    name: str = Field(..., min_length=1, max_length=400)
    object_story_spec: dict


class MetaOperationResponse(BaseModel):
    """Response for Meta API write operations."""
    success: bool
    id: Optional[str] = None
    message: Optional[str] = None
