"""Prediction API endpoints."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_current_user_sync
from app.core.database import get_async_session, sync_session_scope
from app.models.ad import Ad
from app.models.analysis import AdAnalysis
from app.models.user import User
from app.schemas.prediction import (
    FatigueRequest,
    FatigueResponse,
    PredictionRequest,
    PredictionResponse,
    BatchFatigueRequest,
    MLHitScoreRequest,
    MLHitScoreResponse,
)
from app.services.prediction.fatigue_detector import FatigueDetector
from app.services.prediction.ml_scorer import MLHitScorer
from app.services.prediction.performance_predictor import PerformancePredictor

router = APIRouter(prefix="/predictions", tags=["predictions"])


@router.post("/performance", response_model=PredictionResponse)
async def predict_performance(
    request: PredictionRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session),
):
    """Predict CTR, CVR, and winning probability for an ad."""
    # Get ad and analysis
    result = await db.execute(select(Ad).where(Ad.id == request.ad_id))
    ad = result.scalar_one_or_none()
    if not ad:
        raise HTTPException(status_code=404, detail="Ad not found")

    result = await db.execute(
        select(AdAnalysis).where(AdAnalysis.ad_id == request.ad_id)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found. Run analysis first.")

    raw_analysis = analysis.raw_analysis or {}
    video_analysis = raw_analysis.get("video_analysis", {})
    audio_analysis = raw_analysis.get("audio_analysis", {})

    predictor = PerformancePredictor()
    prediction = predictor.predict_performance(
        video_analysis=video_analysis,
        audio_analysis=audio_analysis,
        platform=ad.platform.value if hasattr(ad.platform, 'value') else str(ad.platform),
    )

    return PredictionResponse(ad_id=request.ad_id, **prediction)


@router.post("/fatigue", response_model=FatigueResponse)
async def assess_fatigue(
    request: FatigueRequest,
    _user: dict = Depends(get_current_user_sync),
):
    """Assess ad fatigue based on daily metrics."""
    detector = FatigueDetector()
    assessment = detector.assess_fatigue(
        daily_metrics=request.daily_metrics,
        platform=request.platform,
    )

    return FatigueResponse(
        ad_id=request.ad_id,
        fatigue_score=assessment.fatigue_score,
        days_active=assessment.days_active,
        performance_trend=assessment.performance_trend,
        estimated_remaining_days=assessment.estimated_remaining_days,
        recommendation=assessment.recommendation,
        replacement_urgency=assessment.replacement_urgency,
        metrics_trend=assessment.metrics_trend,
    )


@router.post("/fatigue/batch")
async def batch_assess_fatigue(
    request: BatchFatigueRequest,
    _user: dict = Depends(get_current_user_sync),
):
    """Assess fatigue for multiple ads."""
    detector = FatigueDetector()
    results = detector.batch_assess(
        ads_metrics=request.ads,
        platform=request.platform,
    )

    return {"assessments": results}


@router.post("/hit-score/ml", response_model=MLHitScoreResponse)
async def score_hit_with_ml(
    request: MLHitScoreRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    """Predict hit score using ML scorer with rule-based fallback and A/B routing."""
    scorer = MLHitScorer()
    with sync_session_scope() as session:
        try:
            result = scorer.score_ad(
                session=session,
                ad_id=request.ad_id,
                user_id=current_user.get("user_id"),
                ab_mode=request.ab_mode,
            )
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc))

    return MLHitScoreResponse(**result)
