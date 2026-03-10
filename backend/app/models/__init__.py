"""SQLAlchemy models."""

from app.models.ad import Ad, AdFrame, AdPlatformEnum, MediaExtractionStatus
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
from app.models.creative_asset import (
    GenreTaxonomy,
    CreativeAsset,
    CreativeFamily,
    AdGenreTag,
)
from app.models.conversation import Conversation
from app.models.alert_rule import AlertRule
from app.models.alert_history import AlertHistory
from app.models.data_quality import DataQualitySnapshot

__all__ = [
    "Ad",
    "AdFrame",
    "AdPlatformEnum",
    "MediaExtractionStatus",
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
    "Conversation",
    "AlertRule",
    "AlertHistory",
    "DataQualitySnapshot",
    "GenreTaxonomy",
    "CreativeAsset",
    "CreativeFamily",
    "AdGenreTag",
]
