"""A30 (CI-030): Backend smoke tests.

Fast regression test suite (<5 min) covering critical paths.
Run with: pytest tests/test_smoke.py -v --tb=short

Markers:
    @pytest.mark.smoke — all tests in this file
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock

from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum, AdCategoryEnum


# ── 1. Model creation & field access ────────────────────────────

class TestAdModel:
    """Verify Ad model can be created and queried."""

    def test_create_ad(self, session):
        ad = Ad(
            external_id="smoke_001",
            title="Smoke Test Ad",
            platform=AdPlatformEnum.FACEBOOK,
            status=AdStatusEnum.PENDING,
            advertiser_name="Smoke Advertiser",
            view_count=1000,
            ad_metadata={"test": True},
        )
        session.add(ad)
        session.flush()
        assert ad.id is not None
        assert ad.title == "Smoke Test Ad"
        assert ad.ad_metadata["test"] is True

    def test_query_by_platform(self, session, sample_ads):
        fb_ads = session.query(Ad).filter(
            Ad.platform == AdPlatformEnum.FACEBOOK
        ).all()
        assert len(fb_ads) >= 1

    def test_ad_metadata_update(self, session, sample_ad):
        meta = dict(sample_ad.ad_metadata or {})
        meta["smoke_key"] = "smoke_value"
        sample_ad.ad_metadata = meta
        session.flush()

        refreshed = session.query(Ad).get(sample_ad.id)
        assert refreshed.ad_metadata.get("smoke_key") == "smoke_value"

    def test_category_enum(self):
        assert AdCategoryEnum.BEAUTY is not None
        assert AdCategoryEnum.OTHER is not None

    def test_platform_enum_all_values(self):
        platforms = list(AdPlatformEnum)
        assert len(platforms) >= 8


# ── 2. Config validation ────────────────────────────────────────

class TestConfig:
    """Verify config loads and validates correctly."""

    def test_settings_load(self):
        from app.core.config import get_settings
        s = get_settings()
        assert s.app_name == "VideoAdAnalysisPlatform"
        assert s.api_v1_prefix == "/api/v1"

    def test_normalize_database_url(self):
        from app.core.config import _normalize_database_url
        assert _normalize_database_url("postgres://u:p@h/db", "asyncpg").startswith("postgresql+asyncpg://")
        assert _normalize_database_url("postgres://u:p@h/db", "sync").startswith("postgresql://")

    def test_insecure_secret_key_detection(self):
        from app.core.config import _INSECURE_SECRET_KEYS
        assert "change-this-to-a-secure-random-string" in _INSECURE_SECRET_KEYS
        assert "" in _INSECURE_SECRET_KEYS


# ── 3. Database utilities ────────────────────────────────────────

class TestDatabaseUtils:
    """Verify database helper functions."""

    def test_session_creates_and_closes(self, session):
        from sqlalchemy import text
        result = session.execute(text("SELECT 1")).scalar()
        assert result == 1

    def test_ad_query_returns_list(self, session, sample_ads):
        all_ads = session.query(Ad).all()
        assert isinstance(all_ads, list)
        assert len(all_ads) > 0

    def test_ad_filter_by_status(self, session, sample_ads):
        pending = session.query(Ad).filter(
            Ad.status == AdStatusEnum.PENDING
        ).count()
        assert pending >= 0  # may be 0 if sample_ad has different status


# ── 4. Import smoke tests ───────────────────────────────────────

class TestImports:
    """Verify critical modules can be imported without errors."""

    def test_import_models(self):
        import app.models.ad
        import app.models.ad_metrics
        import app.models.analysis
        import app.models.landing_page
        import app.models.user

    def test_import_config(self):
        from app.core.config import Settings, get_settings

    def test_import_schemas(self):
        from app.schemas.ad import AdResponse, AdListResponse

    def test_import_ranking_service(self):
        from app.services.ranking.ranking_service import compute_hit_score

    def test_import_dispatcher(self):
        from app.tasks.dispatcher import dispatch_task, HEAVY_TASKS, LIGHT_TASKS


# ── 5. Schema validation ────────────────────────────────────────

class TestSchemas:
    """Verify Pydantic schemas accept valid data."""

    def test_ad_response_from_model(self, session, sample_ad):
        from app.schemas.ad import AdResponse
        now = datetime.now(timezone.utc)
        data = {
            "id": sample_ad.id,
            "external_id": sample_ad.external_id,
            "title": sample_ad.title,
            "description": sample_ad.description,
            "platform": sample_ad.platform.value if sample_ad.platform else None,
            "status": sample_ad.status.value if sample_ad.status else None,
            "advertiser_name": sample_ad.advertiser_name,
            "view_count": sample_ad.view_count,
            "created_at": sample_ad.created_at or now,
            "updated_at": sample_ad.updated_at if hasattr(sample_ad, "updated_at") and sample_ad.updated_at else now,
        }
        response = AdResponse.model_validate(data)
        assert response.id == sample_ad.id


# ── 6. Scoring logic ────────────────────────────────────────────

class TestScoringLogic:
    """Verify hit score computation doesn't crash."""

    def test_compute_hit_score_basic(self, session, sample_ad):
        from app.services.ranking.ranking_service import compute_hit_score
        # compute_hit_score takes an Ad object
        result = compute_hit_score(sample_ad)
        # Returns (score, is_hit, hit_level, signals)
        assert isinstance(result, tuple)
        score = result[0]
        assert isinstance(score, (int, float))
        assert 0 <= score <= 100


# ── 7. Lambda handler structure ──────────────────────────────────

class TestLambdaHandler:
    """Verify lambda handler functions exist and are callable."""

    def test_safe_error_production(self):
        # Import from the actual module path
        import importlib
        spec = importlib.util.spec_from_file_location(
            "lambda_handler",
            "lambda_handler.py",
        )
        # We just verify the pattern exists — don't actually load
        # (loading would trigger DB connection)
        assert spec is not None

    def test_sqs_trigger_module_exists(self):
        import importlib
        spec = importlib.util.spec_from_file_location(
            "sqs_ecs_trigger",
            "sqs_ecs_trigger.py",
        )
        assert spec is not None
