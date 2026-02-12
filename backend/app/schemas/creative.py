"""Creative generation schemas."""

from typing import Optional

from pydantic import BaseModel, Field


class ScriptGenerationRequest(BaseModel):
    product_name: str
    product_description: str
    target_audience: str
    duration_seconds: int = Field(default=30, ge=5, le=180)
    structure: str = "problem_solution"
    appeal_axis: str = "benefit"
    platform: str = "youtube"
    tone: str = "friendly"
    reference_ad_id: Optional[int] = None
    language: str = "ja"


class ScriptGenerationResponse(BaseModel):
    title: str
    total_duration_seconds: float
    sections: list[dict]
    thumbnail_concept: str = ""
    hashtags: list[str] = []
    a_b_test_notes: str = ""


class CopyGenerationRequest(BaseModel):
    product_name: str
    product_description: str
    target_audience: str
    platform: str = "facebook"
    appeal_axis: str = "benefit"
    tone: str = "friendly"
    num_variations: int = Field(default=5, ge=1, le=10)
    reference_keywords: Optional[list[str]] = None


class CopyGenerationResponse(BaseModel):
    copies: list[dict]


class LPCopyRequest(BaseModel):
    product_name: str
    product_description: str
    target_audience: str
    appeal_axis: str = "benefit"
    reference_ad_id: Optional[int] = None


class LPCopyResponse(BaseModel):
    hero: dict
    problem_section: str
    solution_section: str
    features: list[dict]
    testimonials: list[dict]
    faq: list[dict]
    final_cta: str


class StoryboardRequest(BaseModel):
    product_name: str
    product_description: str
    target_audience: str
    duration_seconds: int = Field(default=15, ge=5, le=60)
    platform: str = "tiktok"
    style: str = "ugc"


class ImprovementRequest(BaseModel):
    ad_id: int
    current_metrics: Optional[dict] = None


class ABTestPlanRequest(BaseModel):
    ad_id: int
    test_variables: Optional[list[str]] = None
    num_variations: int = Field(default=3, ge=2, le=5)


class WinningPatternRequest(BaseModel):
    winning_ad_id: int
    new_product_name: str
    new_product_description: str
    platform: str = "facebook"
