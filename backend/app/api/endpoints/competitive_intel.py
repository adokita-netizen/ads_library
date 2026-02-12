"""Competitive intelligence API endpoints.

Covers: spend estimation, similarity search, destination analytics,
alert detection, two-stage classification, trend prediction, LP funnels.
"""

from datetime import date, timedelta
from typing import Optional

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from app.api.deps import get_current_user_sync
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.competitive_intel import (
    SpendEstimate,
    CPMCalibration,
    AdEmbedding,
    AlertLog,
    AdClassificationTag,
    TrendPrediction,
    LPFunnel,
    FunnelStep,
    LPFingerprint,
)

logger = structlog.get_logger()
router = APIRouter(prefix="/competitive", tags=["Competitive Intelligence"])


# ==================== Schemas ====================


class SpendEstimateRequest(BaseModel):
    ad_id: int
    view_count_increase: int
    platform: str
    genre: Optional[str] = None


class CPMCalibrationRequest(BaseModel):
    platform: str
    genre: Optional[str] = None
    actual_cpm: float
    actual_cpv: Optional[float] = None
    notes: Optional[str] = None


class SimilaritySearchRequest(BaseModel):
    ad_id: Optional[int] = None
    query_text: Optional[str] = None
    limit: int = Field(20, ge=1, le=100)
    embedding_field: str = Field("combined", pattern="^(combined|text|visual)$")
    min_similarity: float = Field(0.3, ge=0, le=1)


class ClassificationTagRequest(BaseModel):
    ad_id: int
    field_name: str  # genre, product_name, etc.
    value: str
    confidence: float = Field(1.0, ge=0, le=1)
    classified_by: str = "human_review"


class ClassificationConfirmRequest(BaseModel):
    tag_id: int
    confirmed_value: Optional[str] = None  # If different from provisional
    confirmed_by: str = "human_review"


# ==================== Spend Estimation ====================


@router.post("/spend/estimate")
async def estimate_spend(
    request: SpendEstimateRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    """Estimate ad spend with P10/P25/P50/P75/P90 confidence ranges."""
    from app.services.competitive.spend_estimator import SpendEstimator

    session = SyncSessionLocal()
    try:
        estimator = SpendEstimator()
        estimate = estimator.estimate_spend(
            session,
            ad_id=request.ad_id,
            view_count_increase=request.view_count_increase,
            platform=request.platform,
            genre=request.genre,
            user_id=current_user["user_id"],
        )

        return {
            "ad_id": estimate.ad_id,
            "estimated_spend": estimate.estimated_spend,
            "confidence_ranges": {
                "p10": estimate.spend_p10,
                "p25": estimate.spend_p25,
                "p50": estimate.spend_p50,
                "p75": estimate.spend_p75,
                "p90": estimate.spend_p90,
            },
            "cpm_info": {
                "platform_avg": estimate.cpm_platform_avg,
                "genre_adjusted": estimate.cpm_genre_avg,
                "seasonal_factor": estimate.cpm_seasonal_factor,
                "user_calibrated": estimate.cpm_user_calibrated,
            },
            "estimation_method": estimate.estimation_method,
            "confidence_level": estimate.confidence_level,
        }
    finally:
        session.close()


@router.post("/spend/calibrate")
async def save_cpm_calibration(
    request: CPMCalibrationRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    """Save user CPM calibration data for improving spend estimates."""
    from app.services.competitive.spend_estimator import SpendEstimator

    session = SyncSessionLocal()
    try:
        estimator = SpendEstimator()
        calib = estimator.save_calibration(
            session,
            user_id=current_user["user_id"],
            platform=request.platform,
            actual_cpm=request.actual_cpm,
            genre=request.genre,
            actual_cpv=request.actual_cpv,
            notes=request.notes,
        )
        return {
            "id": calib.id,
            "platform": calib.platform,
            "genre": calib.genre,
            "actual_cpm": calib.actual_cpm,
            "message": "CPMキャリブレーションデータを保存しました。今後の推定に反映されます。",
        }
    finally:
        session.close()


@router.get("/spend/calibrations")
async def list_calibrations(
    current_user: dict = Depends(get_current_user_sync),
):
    """List user CPM calibration data."""
    session = SyncSessionLocal()
    try:
        calibs = session.query(CPMCalibration).filter(
            CPMCalibration.user_id == current_user["user_id"]
        ).order_by(CPMCalibration.created_at.desc()).all()
        return {
            "calibrations": [
                {
                    "id": c.id,
                    "platform": c.platform,
                    "genre": c.genre,
                    "actual_cpm": c.actual_cpm,
                    "actual_cpv": c.actual_cpv,
                    "notes": c.notes,
                    "created_at": c.created_at.isoformat(),
                }
                for c in calibs
            ]
        }
    finally:
        session.close()


# ==================== Similarity Search ====================


@router.post("/similarity/search")
async def similarity_search(request: SimilaritySearchRequest):
    """Find similar ads using multimodal embeddings.

    Search by ad_id (find similar to this ad) or query_text (semantic search).
    """
    from app.services.competitive.embedding_service import EmbeddingService

    session = SyncSessionLocal()
    try:
        svc = EmbeddingService()

        if request.ad_id:
            results = svc.find_similar(
                session,
                ad_id=request.ad_id,
                limit=request.limit,
                embedding_field=request.embedding_field,
                min_similarity=request.min_similarity,
            )

            # Enrich with ad info
            for r in results:
                ad = session.query(Ad).filter(Ad.id == r["ad_id"]).first()
                if ad:
                    r["title"] = ad.title
                    r["platform"] = str(ad.platform)
                    r["advertiser_name"] = ad.advertiser_name
                    r["category"] = str(ad.category) if ad.category else None

            return {
                "source_ad_id": request.ad_id,
                "search_type": "similar_ad",
                "results": results,
                "total": len(results),
            }

        elif request.query_text:
            results = svc.search_by_text(
                session,
                query_text=request.query_text,
                limit=request.limit,
                min_similarity=request.min_similarity,
            )

            for r in results:
                ad = session.query(Ad).filter(Ad.id == r["ad_id"]).first()
                if ad:
                    r["title"] = ad.title
                    r["platform"] = str(ad.platform)
                    r["advertiser_name"] = ad.advertiser_name

            return {
                "query_text": request.query_text,
                "search_type": "semantic",
                "results": results,
                "total": len(results),
            }

        raise HTTPException(status_code=400, detail="ad_id or query_text is required")
    finally:
        session.close()


@router.post("/similarity/generate/{ad_id}")
async def generate_embedding(
    ad_id: int,
    current_user: dict = Depends(get_current_user_sync),
):
    """Generate/update embedding for a specific ad."""
    from app.services.competitive.embedding_service import EmbeddingService

    session = SyncSessionLocal()
    try:
        svc = EmbeddingService()
        embedding = svc.generate_embedding(session, ad_id)
        if not embedding:
            raise HTTPException(status_code=404, detail="広告が見つかりません")

        return {
            "ad_id": ad_id,
            "embedding_type": embedding.embedding_type,
            "embedding_dim": embedding.embedding_dim,
            "auto_appeal_axes": embedding.auto_appeal_axes,
            "auto_expression_type": embedding.auto_expression_type,
            "auto_structure_type": embedding.auto_structure_type,
            "message": "エンベディングを生成しました",
        }
    finally:
        session.close()


# ==================== Destination Analytics ====================


@router.get("/destination/lp-reuse")
async def get_lp_reuse(
    genre: Optional[str] = None,
    min_advertisers: int = Query(2, ge=1),
    limit: int = Query(50, ge=1, le=200),
):
    """Find LPs used by multiple advertisers (遷移先アナリティクス)."""
    from app.services.competitive.destination_analytics import DestinationAnalyticsService

    session = SyncSessionLocal()
    try:
        svc = DestinationAnalyticsService()
        results = svc.get_lp_reuse_analytics(session, genre=genre, min_advertisers=min_advertisers, limit=limit)
        return {"total": len(results), "lp_reuse": results}
    finally:
        session.close()


@router.get("/destination/creative-variation/{lp_id}")
async def get_creative_variation(lp_id: int):
    """Analyze creative variations pointing to the same LP."""
    from app.services.competitive.destination_analytics import DestinationAnalyticsService

    session = SyncSessionLocal()
    try:
        svc = DestinationAnalyticsService()
        return svc.get_lp_creative_variation(session, lp_id)
    finally:
        session.close()


@router.get("/destination/advertiser-portfolio/{advertiser_name}")
async def get_advertiser_destinations(advertiser_name: str):
    """Get all destinations used by an advertiser."""
    from app.services.competitive.destination_analytics import DestinationAnalyticsService

    session = SyncSessionLocal()
    try:
        svc = DestinationAnalyticsService()
        return svc.get_advertiser_destination_portfolio(session, advertiser_name)
    finally:
        session.close()


@router.get("/destination/genre-overview/{genre}")
async def get_genre_destination_overview(
    genre: str,
    period_days: int = Query(30, ge=1, le=90),
):
    """Genre-level destination analytics overview."""
    from app.services.competitive.destination_analytics import DestinationAnalyticsService

    session = SyncSessionLocal()
    try:
        svc = DestinationAnalyticsService()
        return svc.get_genre_destination_overview(session, genre, period_days)
    finally:
        session.close()


# ==================== Alert Detection ====================


@router.post("/alerts/detect")
async def run_alert_detection(
    watched_advertisers: Optional[list[str]] = None,
):
    """Run all alert detection algorithms and return new alerts."""
    from app.services.competitive.alert_detector import AlertDetector

    session = SyncSessionLocal()
    try:
        detector = AlertDetector()
        alerts = detector.run_all_detections(session, watched_advertisers=watched_advertisers)

        return {
            "total_alerts": len(alerts),
            "alerts": [
                {
                    "id": a.id,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "entity_type": a.entity_type,
                    "entity_name": a.entity_name,
                    "title": a.title,
                    "description": a.description,
                    "metric_before": a.metric_before,
                    "metric_after": a.metric_after,
                    "change_percent": a.change_percent,
                    "context_data": a.context_data,
                    "detected_at": a.detected_at.isoformat(),
                }
                for a in alerts
            ],
        }
    finally:
        session.close()


@router.get("/alerts/history")
async def get_alert_history(
    alert_type: Optional[str] = None,
    severity: Optional[str] = None,
    days: int = Query(7, ge=1, le=90),
    limit: int = Query(50, ge=1, le=200),
):
    """Get recent alert history."""
    session = SyncSessionLocal()
    try:
        query = session.query(AlertLog).filter(
            AlertLog.detected_at >= date.today() - timedelta(days=days),
        )
        if alert_type:
            query = query.filter(AlertLog.alert_type == alert_type)
        if severity:
            query = query.filter(AlertLog.severity == severity)

        alerts = query.order_by(AlertLog.detected_at.desc()).limit(limit).all()

        return {
            "total": len(alerts),
            "alerts": [
                {
                    "id": a.id,
                    "alert_type": a.alert_type,
                    "severity": a.severity,
                    "entity_type": a.entity_type,
                    "entity_name": a.entity_name,
                    "title": a.title,
                    "description": a.description,
                    "change_percent": a.change_percent,
                    "is_dismissed": a.is_dismissed,
                    "detected_at": a.detected_at.isoformat(),
                }
                for a in alerts
            ],
        }
    finally:
        session.close()


@router.post("/alerts/{alert_id}/dismiss")
async def dismiss_alert(
    alert_id: int,
    current_user: dict = Depends(get_current_user_sync),
):
    """Dismiss an alert."""
    session = SyncSessionLocal()
    try:
        alert = session.query(AlertLog).filter(AlertLog.id == alert_id).first()
        if not alert:
            raise HTTPException(status_code=404, detail="アラートが見つかりません")
        alert.is_dismissed = True
        session.commit()
        return {"message": "アラートを非表示にしました"}
    finally:
        session.close()


# ==================== Two-Stage Classification ====================


@router.get("/classification/tags/{ad_id}")
async def get_classification_tags(ad_id: int):
    """Get all classification tags for an ad (provisional + confirmed)."""
    session = SyncSessionLocal()
    try:
        tags = session.query(AdClassificationTag).filter(
            AdClassificationTag.ad_id == ad_id,
        ).order_by(AdClassificationTag.field_name).all()

        return {
            "ad_id": ad_id,
            "tags": [
                {
                    "id": t.id,
                    "field_name": t.field_name,
                    "value": t.value,
                    "confidence": t.confidence,
                    "status": t.classification_status,
                    "classified_by": t.classified_by,
                    "confirmed_by": t.confirmed_by,
                    "confirmed_at": t.confirmed_at.isoformat() if t.confirmed_at else None,
                    "previous_value": t.previous_value,
                }
                for t in tags
            ],
        }
    finally:
        session.close()


@router.post("/classification/tag")
async def create_classification_tag(
    request: ClassificationTagRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    """Create or update a classification tag for an ad."""
    from datetime import datetime, timezone

    session = SyncSessionLocal()
    try:
        existing = session.query(AdClassificationTag).filter(
            AdClassificationTag.ad_id == request.ad_id,
            AdClassificationTag.field_name == request.field_name,
        ).first()

        if existing:
            existing.previous_value = existing.value
            existing.value = request.value
            existing.confidence = request.confidence
            existing.classified_by = request.classified_by
            if request.classified_by == "human_review":
                existing.classification_status = "confirmed"
                existing.confirmed_by = request.classified_by
                existing.confirmed_at = datetime.now(timezone.utc)
            tag = existing
        else:
            status = "confirmed" if request.classified_by == "human_review" else "provisional"
            tag = AdClassificationTag(
                ad_id=request.ad_id,
                field_name=request.field_name,
                value=request.value,
                confidence=request.confidence,
                classification_status=status,
                classified_by=request.classified_by,
            )
            if status == "confirmed":
                tag.confirmed_by = request.classified_by
                tag.confirmed_at = datetime.now(timezone.utc)
            session.add(tag)

        session.commit()
        session.refresh(tag)

        return {
            "id": tag.id,
            "ad_id": tag.ad_id,
            "field_name": tag.field_name,
            "value": tag.value,
            "status": tag.classification_status,
            "confidence": tag.confidence,
        }
    finally:
        session.close()


@router.post("/classification/confirm")
async def confirm_classification(
    request: ClassificationConfirmRequest,
    current_user: dict = Depends(get_current_user_sync),
):
    """Confirm a provisional classification tag (provisional → confirmed)."""
    from datetime import datetime, timezone

    session = SyncSessionLocal()
    try:
        tag = session.query(AdClassificationTag).filter(
            AdClassificationTag.id == request.tag_id,
        ).first()

        if not tag:
            raise HTTPException(status_code=404, detail="分類タグが見つかりません")

        tag.classification_status = "confirmed"
        tag.confirmed_by = request.confirmed_by
        tag.confirmed_at = datetime.now(timezone.utc)

        if request.confirmed_value and request.confirmed_value != tag.value:
            tag.previous_value = tag.value
            tag.value = request.confirmed_value

        session.commit()
        return {"message": "分類を確定しました", "tag_id": tag.id, "value": tag.value}
    finally:
        session.close()


@router.get("/classification/provisional")
async def list_provisional_tags(
    limit: int = Query(50, ge=1, le=200),
):
    """List all provisional tags awaiting confirmation."""
    session = SyncSessionLocal()
    try:
        tags = (
            session.query(AdClassificationTag)
            .filter(AdClassificationTag.classification_status == "provisional")
            .order_by(AdClassificationTag.confidence.asc())
            .limit(limit)
            .all()
        )

        return {
            "total": len(tags),
            "tags": [
                {
                    "id": t.id,
                    "ad_id": t.ad_id,
                    "field_name": t.field_name,
                    "value": t.value,
                    "confidence": t.confidence,
                    "classified_by": t.classified_by,
                    "created_at": t.created_at.isoformat(),
                }
                for t in tags
            ],
        }
    finally:
        session.close()


# ==================== Trend Prediction ====================


@router.get("/trends/predictions")
async def get_trend_predictions(
    limit: int = Query(50, ge=1, le=200),
):
    """Get trend predictions with velocity analysis and hit probability."""
    from app.services.competitive.trend_predictor import TrendPredictor

    session = SyncSessionLocal()
    try:
        predictor = TrendPredictor()
        predictions = predictor.predict_hits(session, limit=limit)

        return {
            "total": len(predictions),
            "predictions": [
                {
                    "ad_id": p.ad_id,
                    "momentum_score": p.momentum_score,
                    "hit_probability": p.hit_probability,
                    "predicted_hit": p.predicted_hit,
                    "growth_phase": p.growth_phase,
                    "days_active": p.days_since_first_seen,
                    "velocity": {
                        "view_1d": p.view_velocity_1d,
                        "view_3d": p.view_velocity_3d,
                        "view_7d": p.view_velocity_7d,
                        "view_acceleration": p.view_acceleration,
                        "spend_1d": p.spend_velocity_1d,
                        "spend_3d": p.spend_velocity_3d,
                        "spend_7d": p.spend_velocity_7d,
                        "spend_acceleration": p.spend_acceleration,
                    },
                    "genre": p.genre,
                    "genre_percentile": p.genre_percentile,
                    "predicted_peak_spend": p.predicted_peak_spend,
                }
                for p in predictions
            ],
        }
    finally:
        session.close()


@router.get("/trends/early-hits")
async def get_early_hit_candidates(
    max_days_active: int = Query(7, ge=1, le=30),
    min_momentum: float = Query(40, ge=0, le=100),
):
    """Get early hit candidates - ads in first week showing hit potential."""
    from app.services.competitive.trend_predictor import TrendPredictor

    session = SyncSessionLocal()
    try:
        predictor = TrendPredictor()
        candidates = predictor.get_early_hit_candidates(
            session, max_days_active=max_days_active, min_momentum=min_momentum
        )

        # Enrich with ad info
        for c in candidates:
            ad = session.query(Ad).filter(Ad.id == c["ad_id"]).first()
            if ad:
                c["title"] = ad.title
                c["platform"] = str(ad.platform)
                c["advertiser_name"] = ad.advertiser_name

        return {"total": len(candidates), "early_hits": candidates}
    finally:
        session.close()


# ==================== LP Funnels ====================


@router.get("/funnels")
async def list_funnels(
    genre: Optional[str] = None,
    advertiser: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """List detected LP funnels."""
    session = SyncSessionLocal()
    try:
        query = session.query(LPFunnel)
        if genre:
            query = query.filter(LPFunnel.genre == genre)
        if advertiser:
            query = query.filter(LPFunnel.advertiser_name.ilike(f"%{advertiser}%"))

        funnels = query.order_by(LPFunnel.created_at.desc()).limit(limit).all()

        result = []
        for f in funnels:
            steps = session.query(FunnelStep).filter(
                FunnelStep.funnel_id == f.id
            ).order_by(FunnelStep.step_order).all()

            result.append({
                "id": f.id,
                "funnel_name": f.funnel_name,
                "root_domain": f.root_domain,
                "advertiser_name": f.advertiser_name,
                "genre": f.genre,
                "product_name": f.product_name,
                "total_steps": f.total_steps,
                "funnel_type": f.funnel_type,
                "estimated_total_spend": f.estimated_total_spend,
                "ad_count": f.ad_count,
                "steps": [
                    {
                        "step_order": s.step_order,
                        "step_type": s.step_type,
                        "url": s.url,
                        "page_title": s.page_title,
                        "estimated_dropoff_rate": s.estimated_dropoff_rate,
                    }
                    for s in steps
                ],
            })

        return {"total": len(result), "funnels": result}
    finally:
        session.close()


# ==================== LP Fingerprinting ====================


@router.get("/fingerprint/lp/{lp_id}")
async def get_lp_fingerprint(lp_id: int):
    """Get fingerprint and change history for an LP."""
    session = SyncSessionLocal()
    try:
        fingerprints = (
            session.query(LPFingerprint)
            .filter(LPFingerprint.landing_page_id == lp_id)
            .order_by(LPFingerprint.snapshot_date.desc())
            .all()
        )

        return {
            "lp_id": lp_id,
            "snapshots": [
                {
                    "id": fp.id,
                    "snapshot_date": fp.snapshot_date.isoformat(),
                    "content_hash": fp.content_hash,
                    "structure_hash": fp.structure_hash,
                    "offer_fingerprint": fp.offer_fingerprint,
                    "offer_cluster_id": fp.offer_cluster_id,
                    "offer_price": fp.offer_price,
                    "offer_discount_percent": fp.offer_discount_percent,
                    "offer_guarantee_text": fp.offer_guarantee_text,
                    "changes_detected": fp.changes_detected,
                    "change_magnitude": fp.change_magnitude,
                }
                for fp in fingerprints
            ],
        }
    finally:
        session.close()


@router.get("/fingerprint/clusters")
async def get_offer_clusters(
    genre: Optional[str] = None,
    limit: int = Query(50, ge=1, le=200),
):
    """Get offer clusters - groups of LPs with similar offers."""
    from sqlalchemy import func, desc

    session = SyncSessionLocal()
    try:
        query = (
            session.query(
                LPFingerprint.offer_cluster_id,
                func.count(LPFingerprint.id).label("lp_count"),
                func.max(LPFingerprint.offer_price).label("offer_price"),
                func.avg(LPFingerprint.offer_discount_percent).label("avg_discount"),
            )
            .filter(LPFingerprint.offer_cluster_id.isnot(None))
            .group_by(LPFingerprint.offer_cluster_id)
            .order_by(desc("lp_count"))
            .limit(limit)
        )

        clusters = query.all()
        return {
            "total": len(clusters),
            "clusters": [
                {
                    "cluster_id": c.offer_cluster_id,
                    "lp_count": c.lp_count,
                    "offer_price": c.offer_price,
                    "avg_discount_percent": round(c.avg_discount, 1) if c.avg_discount else None,
                }
                for c in clusters
            ],
        }
    finally:
        session.close()
