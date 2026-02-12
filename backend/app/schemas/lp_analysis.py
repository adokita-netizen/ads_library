"""LP Analysis Pydantic schemas."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


# === Request schemas ===

class LPCrawlRequest(BaseModel):
    """Request to crawl and analyze a landing page."""
    url: str
    ad_id: Optional[int] = None
    genre: Optional[str] = None
    product_name: Optional[str] = None
    advertiser_name: Optional[str] = None
    auto_analyze: bool = True


class LPBatchCrawlRequest(BaseModel):
    """Request to crawl multiple LPs (e.g., from ad destinations)."""
    urls: list[str] = Field(..., min_length=1, max_length=50)
    genre: Optional[str] = None
    auto_analyze: bool = True


class LPCompetitorRequest(BaseModel):
    """Request for competitor LP intelligence."""
    genre: str
    limit: int = Field(default=20, ge=1, le=100)


class USPFlowRequest(BaseModel):
    """Request for USP → Article LP flow recommendation."""
    product_name: str
    product_description: str
    target_audience: str
    genre: str
    competitor_lp_ids: Optional[list[int]] = None


# === Response schemas ===

class LPSectionResponse(BaseModel):
    section_order: int
    section_type: str
    heading: Optional[str] = None
    body_text: Optional[str] = None
    has_image: bool = False
    has_video: bool = False
    has_cta: bool = False
    cta_text: Optional[str] = None
    position_y_percent: Optional[float] = None

    model_config = {"from_attributes": True}


class USPPatternResponse(BaseModel):
    id: int
    usp_category: str
    usp_text: str
    usp_headline: Optional[str] = None
    supporting_evidence: Optional[str] = None
    prominence_score: Optional[float] = None
    position_in_page: Optional[str] = None
    keywords: Optional[list[str]] = None

    model_config = {"from_attributes": True}


class AppealAxisResponse(BaseModel):
    appeal_axis: str
    strength_score: float
    evidence_texts: Optional[list[str]] = None

    model_config = {"from_attributes": True}


class LPAnalysisDetailResponse(BaseModel):
    overall_quality_score: Optional[float] = None
    conversion_potential_score: Optional[float] = None
    trust_score: Optional[float] = None
    urgency_score: Optional[float] = None
    page_flow_pattern: Optional[str] = None
    structure_summary: Optional[str] = None
    inferred_target_gender: Optional[str] = None
    inferred_target_age_range: Optional[str] = None
    inferred_target_concerns: Optional[list[str]] = None
    target_persona_summary: Optional[str] = None
    primary_appeal_axis: Optional[str] = None
    secondary_appeal_axis: Optional[str] = None
    appeal_strategy_summary: Optional[str] = None
    competitive_positioning: Optional[str] = None
    differentiation_points: Optional[list[str]] = None
    headline_effectiveness: Optional[float] = None
    cta_effectiveness: Optional[float] = None
    emotional_triggers: Optional[list[str]] = None
    power_words: Optional[list[str]] = None
    strengths: Optional[list[str]] = None
    weaknesses: Optional[list[str]] = None
    reusable_patterns: Optional[list[str]] = None
    improvement_suggestions: Optional[list[str]] = None
    full_analysis_text: Optional[str] = None

    model_config = {"from_attributes": True}


class LPResponse(BaseModel):
    id: int
    url: str
    final_url: Optional[str] = None
    domain: Optional[str] = None
    title: Optional[str] = None
    meta_description: Optional[str] = None
    lp_type: str
    genre: Optional[str] = None
    advertiser_name: Optional[str] = None
    product_name: Optional[str] = None
    status: str

    # Content metrics
    word_count: Optional[int] = None
    image_count: Optional[int] = None
    cta_count: Optional[int] = None
    testimonial_count: Optional[int] = None
    estimated_read_time_seconds: Optional[int] = None

    # Extracted content
    hero_headline: Optional[str] = None
    hero_subheadline: Optional[str] = None
    primary_cta_text: Optional[str] = None
    has_pricing: Optional[bool] = None
    price_text: Optional[str] = None

    crawled_at: Optional[datetime] = None
    analyzed_at: Optional[datetime] = None
    created_at: datetime

    model_config = {"from_attributes": True}


class LPDetailResponse(LPResponse):
    """Full LP detail with sections, USPs, appeals, and analysis."""
    sections: list[LPSectionResponse] = []
    usp_patterns: list[USPPatternResponse] = []
    appeal_axes: list[AppealAxisResponse] = []
    analysis: Optional[LPAnalysisDetailResponse] = None


class LPListResponse(BaseModel):
    landing_pages: list[LPResponse]
    total: int
    page: int
    page_size: int


class CompetitorAppealPatternResponse(BaseModel):
    appeal_axis: str
    avg_strength: float
    usage_count: int
    sample_texts: list[str] = []


class GenreInsightResponse(BaseModel):
    genre: str
    total_lps_analyzed: int
    dominant_appeal: str
    appeal_distribution: list[CompetitorAppealPatternResponse] = []
    common_usps: list[dict] = []
    avg_quality_score: float = 0.0
    common_structures: list[str] = []
    target_personas: list[dict] = []
    recommendations: list[str] = []


class USPFlowResponse(BaseModel):
    recommended_primary_usp: str
    recommended_appeal_axis: str
    article_lp_structure: list[dict] = []
    headline_suggestions: list[str] = []
    differentiation_opportunities: list[str] = []
    competitor_gaps: list[str] = []
    estimated_effectiveness: float = 0.0
    reasoning: str = ""


class LPTaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
