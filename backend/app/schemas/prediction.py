"""Prediction schemas."""

from pydantic import BaseModel, Field


class PredictionRequest(BaseModel):
    ad_id: int


class PredictionResponse(BaseModel):
    ad_id: int
    predicted_ctr: float
    ctr_confidence: dict
    predicted_cvr: float
    cvr_confidence: dict
    winning_probability: float
    optimal_duration_seconds: float
    feature_importance: list[dict]
    improvement_suggestions: list[dict]
    model_version: str


class FatigueRequest(BaseModel):
    ad_id: int
    daily_metrics: list[dict]
    platform: str = "youtube"


class FatigueResponse(BaseModel):
    ad_id: int
    fatigue_score: float
    days_active: int
    performance_trend: str
    estimated_remaining_days: int
    recommendation: str
    replacement_urgency: str
    metrics_trend: dict


class BatchFatigueRequest(BaseModel):
    ads: list[dict]
    platform: str = "youtube"


class MLHitScoreRequest(BaseModel):
    ad_id: int
    ab_mode: str = Field(default="auto", pattern="^(auto|rule|ml)$")


class MLHitScoreResponse(BaseModel):
    ad_id: int
    ab_mode: str
    ab_arm: str
    model_version: str
    rule_score: float
    ml_score: float | None = None
    selected_score: float
    rule_hit: bool
    rule_level: str
    trained_now: bool = False
    train_info: dict = Field(default_factory=dict)
