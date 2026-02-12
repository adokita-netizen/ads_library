"""Tests for competitive intelligence services."""

import math
from datetime import date, datetime, timezone

import pytest
from sqlalchemy.orm import Session

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.models.competitive_intel import (
    SpendEstimate,
    CPMCalibration,
    AdEmbedding,
    AlertLog,
    AdClassificationTag,
    TrendPrediction,
)
from app.services.competitive.spend_estimator import (
    SpendEstimator,
    PLATFORM_CPM_DEFAULTS,
    GENRE_CPM_MULTIPLIERS,
    SEASONAL_FACTORS,
)
from app.services.competitive.embedding_service import (
    EmbeddingService,
    _simple_text_hash,
    _cosine_similarity,
    _detect_appeal_axes,
    _detect_expression_type,
)
from app.services.competitive.alert_detector import AlertDetector
from app.services.competitive.trend_predictor import TrendPredictor


class TestSpendEstimator:
    """Test spend estimation service."""

    def test_platform_cpm_defaults_complete(self):
        """All platforms should have CPM defaults."""
        expected = [
            "youtube", "tiktok", "instagram", "facebook",
            "x_twitter", "line", "yahoo",
            "pinterest", "smartnews", "google_ads", "gunosy",
        ]
        for p in expected:
            assert p in PLATFORM_CPM_DEFAULTS, f"Missing CPM default for {p}"
            assert "avg" in PLATFORM_CPM_DEFAULTS[p]
            assert "std" in PLATFORM_CPM_DEFAULTS[p]
            assert PLATFORM_CPM_DEFAULTS[p]["avg"] > 0

    def test_seasonal_factors_all_months(self):
        """All 12 months should have seasonal factors."""
        for month in range(1, 13):
            assert month in SEASONAL_FACTORS
            assert 0.5 < SEASONAL_FACTORS[month] < 2.0

    def test_estimate_spend_basic(self, sample_ad, session: Session):
        estimator = SpendEstimator()
        estimate = estimator.estimate_spend(
            session=session,
            ad_id=sample_ad.id,
            view_count_increase=10000,
            platform="youtube",
        )

        assert isinstance(estimate, SpendEstimate)
        assert estimate.estimated_spend > 0
        assert estimate.spend_p10 > 0
        assert estimate.spend_p10 <= estimate.spend_p25
        assert estimate.spend_p25 <= estimate.spend_p50
        assert estimate.spend_p50 <= estimate.spend_p75
        assert estimate.spend_p75 <= estimate.spend_p90
        assert estimate.estimation_method == "cpm_model"
        assert estimate.confidence_level == 0.45

    def test_estimate_spend_with_genre(self, sample_ad, session: Session):
        estimator = SpendEstimator()
        est_no_genre = estimator.estimate_spend(
            session=session,
            ad_id=sample_ad.id,
            view_count_increase=10000,
            platform="youtube",
        )
        est_beauty = estimator.estimate_spend(
            session=session,
            ad_id=sample_ad.id,
            view_count_increase=10000,
            platform="youtube",
            genre="美容・コスメ",
        )

        # Beauty genre has 1.3x multiplier, so spend should be higher
        assert est_beauty.estimated_spend > est_no_genre.estimated_spend

    def test_estimate_spend_all_platforms(self, sample_ad, session: Session):
        estimator = SpendEstimator()
        for platform in PLATFORM_CPM_DEFAULTS:
            estimate = estimator.estimate_spend(
                session=session,
                ad_id=sample_ad.id,
                view_count_increase=10000,
                platform=platform,
            )
            assert estimate.estimated_spend > 0, f"Failed for platform {platform}"

    def test_estimate_zero_views(self, sample_ad, session: Session):
        estimator = SpendEstimator()
        estimate = estimator.estimate_spend(
            session=session,
            ad_id=sample_ad.id,
            view_count_increase=0,
            platform="youtube",
        )
        assert estimate.estimated_spend == 0
        assert estimate.spend_p50 == 0

    def test_save_calibration(self, session: Session):
        from app.models.user import User
        user = User(
            email="test@example.com",
            full_name="Test User",
            hashed_password="fakehash",
        )
        session.add(user)
        session.flush()

        estimator = SpendEstimator()
        calib = estimator.save_calibration(
            session=session,
            user_id=user.id,
            platform="youtube",
            actual_cpm=350.0,
            genre="美容・コスメ",
            notes="自社キャンペーンの実績値",
        )

        assert calib.id is not None
        assert calib.actual_cpm == 350.0
        assert calib.platform == "youtube"


class TestEmbeddingService:
    """Test embedding service and utility functions."""

    def test_simple_text_hash(self):
        embedding = _simple_text_hash("テスト広告")
        assert len(embedding) == 128
        assert all(isinstance(x, float) for x in embedding)

    def test_simple_text_hash_empty(self):
        embedding = _simple_text_hash("")
        assert len(embedding) == 128
        assert all(x == 0.0 for x in embedding)

    def test_simple_text_hash_normalized(self):
        embedding = _simple_text_hash("テスト広告テキスト")
        magnitude = math.sqrt(sum(x * x for x in embedding))
        assert abs(magnitude - 1.0) < 0.01  # Should be unit vector

    def test_simple_text_hash_custom_dim(self):
        embedding = _simple_text_hash("test", dim=64)
        assert len(embedding) == 64

    def test_cosine_similarity_identical(self):
        vec = [1.0, 0.0, 0.0]
        assert _cosine_similarity(vec, vec) == pytest.approx(1.0)

    def test_cosine_similarity_orthogonal(self):
        vec_a = [1.0, 0.0, 0.0]
        vec_b = [0.0, 1.0, 0.0]
        assert _cosine_similarity(vec_a, vec_b) == pytest.approx(0.0)

    def test_cosine_similarity_opposite(self):
        vec_a = [1.0, 0.0]
        vec_b = [-1.0, 0.0]
        assert _cosine_similarity(vec_a, vec_b) == pytest.approx(-1.0)

    def test_cosine_similarity_empty(self):
        assert _cosine_similarity([], []) == 0.0

    def test_cosine_similarity_mismatched(self):
        assert _cosine_similarity([1.0], [1.0, 2.0]) == 0.0

    def test_detect_appeal_axes(self):
        text = "効果を実感！口コミ評価No.1の医師監修サプリ"
        axes = _detect_appeal_axes(text)
        assert "benefit" in axes  # 効果, 実感
        assert "social_proof" in axes  # 口コミ, 評価
        assert "authority" in axes  # 医師, 監修

    def test_detect_appeal_axes_empty(self):
        axes = _detect_appeal_axes("")
        assert axes == []

    def test_detect_appeal_axes_urgency(self):
        text = "今だけ限定！初回無料キャンペーン"
        axes = _detect_appeal_axes(text)
        assert "urgency" in axes  # 限定, 今だけ
        assert "price" in axes  # 初回, 無料

    def test_detect_expression_type_ugc(self):
        text = "使ってみた正直レビュー"
        expr = _detect_expression_type(text)
        assert expr == "ugc"

    def test_detect_expression_type_comparison(self):
        text = "vs比較対決 どっちが良い？"
        expr = _detect_expression_type(text)
        assert expr == "comparison"

    def test_detect_expression_type_empty(self):
        expr = _detect_expression_type("")
        assert expr is None

    def test_text_similarity_same_content(self):
        """Similar texts should have higher similarity."""
        emb_a = _simple_text_hash("美容クリーム効果")
        emb_b = _simple_text_hash("美容クリーム効果")
        emb_c = _simple_text_hash("金融投資ゲーム")

        sim_same = _cosine_similarity(emb_a, emb_b)
        sim_diff = _cosine_similarity(emb_a, emb_c)

        assert sim_same > sim_diff


class TestAlertDetector:
    """Test alert detection service."""

    def test_instantiation(self):
        detector = AlertDetector()
        assert detector is not None

    def test_run_all_detections_empty_db(self, session: Session):
        detector = AlertDetector()
        alerts = detector.run_all_detections(session)
        # Should not crash on empty database
        assert isinstance(alerts, list)

    def test_detect_spend_surges_empty(self, session: Session):
        detector = AlertDetector()
        alerts = detector.detect_spend_surges(session)
        assert isinstance(alerts, list)
        assert len(alerts) == 0

    def test_detect_lp_swaps_empty(self, session: Session):
        detector = AlertDetector()
        alerts = detector.detect_lp_swaps(session)
        assert isinstance(alerts, list)
        assert len(alerts) == 0

    def test_detect_new_competitor_ads_empty(self, session: Session):
        detector = AlertDetector()
        alerts = detector.detect_new_competitor_ads(
            session, watched_advertisers=["テスト株式会社"]
        )
        assert isinstance(alerts, list)
        assert len(alerts) == 0

    def test_detect_category_trends_empty(self, session: Session):
        detector = AlertDetector()
        alerts = detector.detect_category_trends(session)
        assert isinstance(alerts, list)
        assert len(alerts) == 0


class TestTrendPredictor:
    """Test trend prediction service."""

    def test_instantiation(self):
        predictor = TrendPredictor()
        assert predictor is not None

    def test_detect_growth_phase_launch(self):
        predictor = TrendPredictor()
        phase = predictor._detect_growth_phase(
            vel_1d=100, vel_3d=200, vel_7d=300,
            acceleration=2.0, days_active=2,
        )
        # days_active <= 3 => launch
        assert phase == "launch"

    def test_detect_growth_phase_growth(self):
        predictor = TrendPredictor()
        phase = predictor._detect_growth_phase(
            vel_1d=500, vel_3d=300, vel_7d=200,
            acceleration=0.5, days_active=10,
        )
        assert phase == "growth"

    def test_detect_growth_phase_decline(self):
        predictor = TrendPredictor()
        phase = predictor._detect_growth_phase(
            vel_1d=50, vel_3d=200, vel_7d=1000,
            acceleration=-0.5, days_active=30,
        )
        assert phase in ["decline", "plateau"]

    def test_calculate_hit_probability(self):
        predictor = TrendPredictor()
        velocity = {
            "view_velocity_1d": 5000,
            "view_velocity_7d": 3000,
            "view_acceleration": 0.6,
            "spend_velocity_1d": 60000,
            "spend_velocity_7d": 40000,
            "spend_acceleration": 0.4,
            "growth_phase": "growth",
        }
        prob = predictor._calculate_hit_probability(velocity, genre_percentile=85.0)
        assert 0.0 <= prob <= 1.0

    def test_calculate_momentum_score(self):
        predictor = TrendPredictor()
        velocity = {
            "view_velocity_1d": 5000,
            "view_velocity_7d": 6000,
            "view_acceleration": 1.5,
            "spend_velocity_1d": 100000,
            "spend_velocity_7d": 80000,
            "spend_acceleration": 0.5,
            "growth_phase": "growth",
        }
        score = predictor._calculate_momentum_score(velocity, genre_percentile=80.0)
        assert 0 <= score <= 100

    def test_momentum_score_zero_inputs(self):
        predictor = TrendPredictor()
        velocity = {
            "view_velocity_1d": 0,
            "view_velocity_7d": 0,
            "view_acceleration": 0,
            "spend_velocity_1d": 0,
            "spend_velocity_7d": 0,
            "spend_acceleration": 0,
            "growth_phase": "decline",
        }
        score = predictor._calculate_momentum_score(velocity, genre_percentile=0)
        assert score >= 0
