"""Tests for database models - Ad, CompetitiveIntel models."""

from datetime import datetime, date, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum, AdCategoryEnum
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


class TestAdPlatformEnum:
    """Test that all 12 platform enum values are defined correctly."""

    def test_all_platforms_defined(self):
        platforms = [e.value for e in AdPlatformEnum]
        assert "youtube" in platforms
        assert "tiktok" in platforms
        assert "instagram" in platforms
        assert "facebook" in platforms
        assert "x_twitter" in platforms
        assert "line" in platforms
        assert "yahoo" in platforms
        assert "pinterest" in platforms
        assert "smartnews" in platforms
        assert "google_ads" in platforms
        assert "gunosy" in platforms
        assert "other" in platforms

    def test_platform_count(self):
        assert len(AdPlatformEnum) == 12

    def test_enum_string_equality(self):
        assert AdPlatformEnum.YOUTUBE == "youtube"
        assert AdPlatformEnum.PINTEREST == "pinterest"
        assert AdPlatformEnum.SMARTNEWS == "smartnews"
        assert AdPlatformEnum.GOOGLE_ADS == "google_ads"
        assert AdPlatformEnum.GUNOSY == "gunosy"


class TestAdModel:
    """Test Ad model CRUD operations."""

    def test_create_ad(self, session: Session):
        ad = Ad(
            title="Test Ad",
            platform=AdPlatformEnum.YOUTUBE,
            status=AdStatusEnum.PENDING,
        )
        session.add(ad)
        session.commit()
        session.refresh(ad)

        assert ad.id is not None
        assert ad.title == "Test Ad"
        assert ad.platform == AdPlatformEnum.YOUTUBE
        assert ad.created_at is not None

    def test_create_ad_all_platforms(self, sample_ads, session: Session):
        """Verify ads can be created for every platform."""
        assert len(sample_ads) == 11
        for ad in sample_ads:
            assert ad.id is not None
            assert ad.platform in AdPlatformEnum

    def test_ad_metadata_jsonb(self, session: Session):
        ad = Ad(
            title="Metadata Test",
            platform=AdPlatformEnum.SMARTNEWS,
            ad_metadata={"genre": "美容", "campaign_id": "c123"},
            tags=["beauty", "skincare"],
        )
        session.add(ad)
        session.commit()
        session.refresh(ad)

        assert ad.ad_metadata["genre"] == "美容"
        assert "beauty" in ad.tags

    def test_ad_nullable_fields(self, session: Session):
        ad = Ad(
            platform=AdPlatformEnum.GUNOSY,
            status=AdStatusEnum.PENDING,
        )
        session.add(ad)
        session.commit()

        assert ad.title is None
        assert ad.description is None
        assert ad.video_url is None
        assert ad.view_count is None


class TestSpendEstimateModel:
    """Test SpendEstimate model."""

    def test_create_spend_estimate(self, sample_ad, session: Session):
        estimate = SpendEstimate(
            ad_id=sample_ad.id,
            estimate_date=date.today(),
            view_count=100000,
            view_count_increase=5000,
            platform="youtube",
            genre="美容・コスメ",
            cpm_platform_avg=400.0,
            cpm_genre_avg=520.0,
            cpm_seasonal_factor=1.0,
            estimated_spend=2600.0,
            spend_p10=1800.0,
            spend_p25=2100.0,
            spend_p50=2600.0,
            spend_p75=3200.0,
            spend_p90=3800.0,
            estimation_method="cpm_model",
            confidence_level=0.45,
        )
        session.add(estimate)
        session.commit()
        session.refresh(estimate)

        assert estimate.id is not None
        assert estimate.spend_p50 == 2600.0
        assert estimate.confidence_level == 0.45


class TestAlertLogModel:
    """Test AlertLog model."""

    def test_create_alert(self, session: Session):
        alert = AlertLog(
            alert_type="spend_surge",
            severity="high",
            entity_type="ad",
            entity_id=1,
            entity_name="テスト広告",
            title="消化額急増: テスト広告 (300%増)",
            description="直近3日間の予想消化額が前期間比3.0倍に急増",
            metric_before=10000,
            metric_after=30000,
            change_percent=200.0,
        )
        session.add(alert)
        session.commit()
        session.refresh(alert)

        assert alert.id is not None
        assert alert.alert_type == "spend_surge"
        assert alert.severity == "high"
        assert alert.is_dismissed is False


class TestAdEmbeddingModel:
    """Test AdEmbedding model."""

    def test_create_embedding(self, sample_ad, session: Session):
        embedding = AdEmbedding(
            ad_id=sample_ad.id,
            visual_embedding=[0.1] * 128,
            text_embedding=[0.2] * 128,
            combined_embedding=[0.15] * 128,
            embedding_type="multimodal",
            embedding_dim=128,
            model_version="hash_v1",
            auto_appeal_axes=["benefit", "social_proof"],
            auto_expression_type="ugc",
        )
        session.add(embedding)
        session.commit()
        session.refresh(embedding)

        assert embedding.id is not None
        assert len(embedding.combined_embedding) == 128
        assert "benefit" in embedding.auto_appeal_axes


class TestAdClassificationTagModel:
    """Test two-stage classification model."""

    def test_create_provisional_tag(self, sample_ad, session: Session):
        tag = AdClassificationTag(
            ad_id=sample_ad.id,
            field_name="genre",
            value="美容・コスメ",
            classification_status="provisional",
            confidence=0.85,
            classified_by="auto_fast",
        )
        session.add(tag)
        session.commit()
        session.refresh(tag)

        assert tag.classification_status == "provisional"
        assert tag.confirmed_by is None

    def test_confirm_tag(self, sample_ad, session: Session):
        tag = AdClassificationTag(
            ad_id=sample_ad.id,
            field_name="genre",
            value="美容・コスメ",
            classification_status="provisional",
            confidence=0.85,
            classified_by="auto_fast",
        )
        session.add(tag)
        session.commit()

        # Confirm the tag
        tag.classification_status = "confirmed"
        tag.confirmed_by = "human_reviewer"
        session.commit()
        session.refresh(tag)

        assert tag.classification_status == "confirmed"
        assert tag.confirmed_by == "human_reviewer"


class TestTrendPredictionModel:
    """Test TrendPrediction model."""

    def test_create_trend_prediction(self, sample_ad, session: Session):
        prediction = TrendPrediction(
            ad_id=sample_ad.id,
            prediction_date=date.today(),
            view_velocity_1d=500.0,
            view_velocity_3d=1200.0,
            view_velocity_7d=3500.0,
            view_acceleration=1.5,
            growth_phase="growth",
            genre_avg_velocity=800.0,
            genre_percentile=85.0,
            hit_probability=0.72,
            momentum_score=78.5,
        )
        session.add(prediction)
        session.commit()
        session.refresh(prediction)

        assert prediction.id is not None
        assert prediction.growth_phase == "growth"
        assert prediction.momentum_score == 78.5
