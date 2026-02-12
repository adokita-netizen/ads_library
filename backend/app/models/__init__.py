"""SQLAlchemy models."""

from app.models.ad import Ad, AdFrame, AdPlatformEnum
from app.models.analysis import (
    AdAnalysis,
    DetectedObject,
    SceneBoundary,
    SentimentResult,
    TextDetection,
    Transcription,
)
from app.models.campaign import Campaign, CampaignAd
from app.models.creative import GeneratedCreative, CreativeTemplate
from app.models.prediction import PerformancePrediction, AdFatigueLog
from app.models.user import User

__all__ = [
    "Ad",
    "AdFrame",
    "AdPlatformEnum",
    "AdAnalysis",
    "DetectedObject",
    "SceneBoundary",
    "SentimentResult",
    "TextDetection",
    "Transcription",
    "Campaign",
    "CampaignAd",
    "GeneratedCreative",
    "CreativeTemplate",
    "PerformancePrediction",
    "AdFatigueLog",
    "User",
]
