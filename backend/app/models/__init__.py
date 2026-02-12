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
from app.models.landing_page import (
    LandingPage,
    LPSection,
    USPPattern,
    AppealAxisAnalysis,
    LPAnalysis,
)
from app.models.ad_metrics import (
    AdDailyMetrics,
    ProductRanking,
    NotificationConfig,
    SavedItem,
)
from app.models.competitive_intel import (
    SpendEstimate,
    CPMCalibration,
    AdEmbedding,
    LPFingerprint,
    AlertLog,
    AdClassificationTag,
    LPFunnel,
    FunnelStep,
    TrendPrediction,
)

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
    "LandingPage",
    "LPSection",
    "USPPattern",
    "AppealAxisAnalysis",
    "LPAnalysis",
    "AdDailyMetrics",
    "ProductRanking",
    "NotificationConfig",
    "SavedItem",
    "SpendEstimate",
    "CPMCalibration",
    "AdEmbedding",
    "LPFingerprint",
    "AlertLog",
    "AdClassificationTag",
    "LPFunnel",
    "FunnelStep",
    "TrendPrediction",
]
