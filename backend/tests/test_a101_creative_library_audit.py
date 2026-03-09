from datetime import date, datetime, timezone

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.api.deps import get_current_user
from app.api.endpoints import data_quality
from app.core.database import Base, get_async_session
import app.services.data_quality_report as data_quality_report

from app.models.ad import Ad, AdCategoryEnum, AdPlatformEnum, AdStatusEnum
from app.services.data_quality_report import build_creative_library_audit


def _mk_ad(
    external_id: str,
    *,
    platform: AdPlatformEnum,
    category=None,
    title: str = "ad",
    image_url: str | None = None,
    thumbnail_url: str | None = None,
    video_url: str | None = None,
    image_s3_key: str | None = None,
    s3_key: str | None = None,
    destination_url: str | None = None,
    metadata: dict | None = None,
    updated_at: datetime | None = None,
) -> Ad:
    return Ad(
        external_id=external_id,
        title=title,
        platform=platform,
        status=AdStatusEnum.PENDING,
        category=category,
        image_url=image_url,
        thumbnail_url=thumbnail_url,
        video_url=video_url,
        image_s3_key=image_s3_key,
        s3_key=s3_key,
        destination_url=destination_url,
        advertiser_name="audit tester",
        ad_metadata=metadata or {},
        updated_at=updated_at or datetime.now(timezone.utc),
    )


def test_a101_creative_library_audit_builds_kpi_and_deltas(session, monkeypatch, tmp_path):
    monkeypatch.setattr(data_quality_report, "_AUDIT_REPORTS_FILE", tmp_path / "creative_library_audit_reports.json")
    monkeypatch.setattr(data_quality_report, "_load_expected_keywords", lambda: ["beauty", "finance"])

    session.add_all([
        _mk_ad(
            "a101_complete",
            platform=AdPlatformEnum.FACEBOOK,
            category=AdCategoryEnum.BEAUTY,
            title="complete",
            image_url="https://example.com/creative.jpg",
            image_s3_key="images/1.jpg",
            destination_url="https://example.com/lp",
            updated_at=datetime(2026, 3, 8, 10, tzinfo=timezone.utc),
        ),
        _mk_ad(
            "a101_missing_media",
            platform=AdPlatformEnum.INSTAGRAM,
            category=AdCategoryEnum.FINANCE,
            title="missing media",
            destination_url="https://example.com/finance",
            updated_at=datetime(2026, 3, 8, 11, tzinfo=timezone.utc),
        ),
        _mk_ad(
            "a101_stale_download",
            platform=AdPlatformEnum.INSTAGRAM,
            category=AdCategoryEnum.FINANCE,
            title="stale",
            image_url="https://example.com/stale.jpg",
            metadata={"snapshot_check": {"reachable": False}},
            updated_at=datetime(2026, 3, 8, 12, tzinfo=timezone.utc),
        ),
    ])
    session.commit()

    first = build_creative_library_audit(session, target_date=date(2026, 3, 7), persist=True)["creative_library_audit"]
    second = build_creative_library_audit(session, target_date=date(2026, 3, 8), persist=True)["creative_library_audit"]

    assert first["summary"]["total_ads"] == 3
    assert first["summary"]["creative_viewable_rate"] == pytest.approx(2 / 3, rel=1e-4)
    assert first["summary"]["creative_downloadable_rate"] == pytest.approx(1 / 3, rel=1e-4)
    assert first["summary"]["lp_present_rate"] == pytest.approx(2 / 3, rel=1e-4)
    assert first["summary"]["lp_resolved_rate"] == pytest.approx(0.0, rel=1e-4)
    assert first["failure_reason_counts"]["missing_creative"] == 1
    assert first["failure_reason_counts"]["missing_lp"] == 1
    assert first["failure_reason_counts"]["stale_snapshot"] == 1
    assert first["failure_reason_counts"]["not_downloadable"] == 1
    assert first["failure_reason_counts"]["lp_unresolved"] == 2
    assert first["priority_recovery_ads"][0]["title"] == "stale"
    assert first["priority_recovery_ads"][0]["needs_download_recovery"] is True
    assert first["creative_library_gap_audit"]["summary"]["lp_resolved_rate"] == pytest.approx(0.0, rel=1e-4)
    assert first["slo_status"]["overall_status"] in {"warning", "critical"}
    assert "live_ingestion_audit" in first
    assert "creative_library_daily_report" in first
    assert "ops_alert_candidates" in first

    finance_row = next(row for row in first["genre_breakdown"] if row["label"] == "finance")
    assert finance_row["missing_media_count"] == 1
    assert finance_row["download_unavailable_count"] == 1
    assert finance_row["lp_unresolved_count"] == 1

    assert second["deltas"]["summary"]["missing_media_count"] == 0
    assert any(row["label"] == "instagram" for row in second["deltas"]["platform_breakdown"])


@pytest.mark.asyncio
async def test_a101_creative_library_audit_endpoint_returns_contract():
    engine = create_async_engine("sqlite+aiosqlite://", echo=False)

    async def override_async_session():
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        AsyncTestSession = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        async with AsyncTestSession() as db:
            existing = await db.get(Ad, 1)
            if existing is None:
                db.add(
                    Ad(
                        external_id="a101_api",
                        title="api",
                        platform=AdPlatformEnum.FACEBOOK,
                        status=AdStatusEnum.PENDING,
                        image_url="https://example.com/api.jpg",
                        destination_url="https://example.com/lp",
                        advertiser_name="api tester",
                        ad_metadata={},
                    )
                )
                await db.commit()
            yield db

    async def override_current_user():
        return {"user_id": 1, "email": "test@example.com"}

    app = FastAPI()
    app.include_router(data_quality.router, prefix="/api/v1")
    app.dependency_overrides[get_async_session] = override_async_session
    app.dependency_overrides[get_current_user] = override_current_user

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac:
        res = await ac.get("/api/v1/data-quality/creative-library-audit?top_n=5")

    assert res.status_code == 200
    payload = res.json()
    assert "creative_library_audit" in payload
    assert payload["creative_library_audit"]["summary"]["total_ads"] >= 1
    assert "platform_breakdown" in payload["creative_library_audit"]
    assert "genre_breakdown" in payload["creative_library_audit"]
    assert "priority_recovery_ads" in payload["creative_library_audit"]
    assert "creative_library_daily_report" in payload["creative_library_audit"]
    assert "live_ingestion_audit" in payload["creative_library_audit"]


def test_a102_a105_creative_ops_and_live_ingestion_reports(session, monkeypatch, tmp_path):
    monkeypatch.setattr(data_quality_report, "_AUDIT_REPORTS_FILE", tmp_path / "creative_library_audit_reports.json")
    monkeypatch.setattr(data_quality_report, "_load_expected_keywords", lambda: ["beauty", "finance", "sleep"])

    session.add_all([
        _mk_ad(
            "a102_regress",
            platform=AdPlatformEnum.FACEBOOK,
            category=AdCategoryEnum.BEAUTY,
            title="same creative",
            image_url="https://example.com/creative.jpg",
            image_s3_key="images/regress.jpg",
            destination_url="https://example.com/beauty",
            metadata={"last_crawl_keyword": "beauty", "lp_data": {"final_url": "https://example.com/beauty-final"}},
            updated_at=datetime(2026, 3, 7, 8, tzinfo=timezone.utc),
        ),
        _mk_ad(
            "a102_recover",
            platform=AdPlatformEnum.INSTAGRAM,
            category=AdCategoryEnum.FINANCE,
            title="recover target",
            image_url="https://example.com/finance.jpg",
            destination_url="https://example.com/finance",
            metadata={"last_crawl_keyword": "finance"},
            updated_at=datetime(2026, 3, 7, 9, tzinfo=timezone.utc),
        ),
    ])
    session.commit()

    first = build_creative_library_audit(session, target_date=date(2026, 3, 7), persist=True)["creative_library_audit"]
    assert first["creative_library_daily_report"]["top_regressions"] == []
    assert first["creative_library_daily_report"]["top_recoveries"] == []

    regress_ad = session.query(Ad).filter(Ad.external_id == "a102_regress").one()
    regress_ad.image_s3_key = None
    regress_ad.ad_metadata = {"last_crawl_keyword": "beauty", "lp_data": {"final_url": "https://example.com/beauty-final"}}

    recover_ad = session.query(Ad).filter(Ad.external_id == "a102_recover").one()
    recover_ad.image_s3_key = "images/recover.jpg"
    recover_ad.ad_metadata = {
        "last_crawl_keyword": "finance",
        "lp_data": {"final_url": "https://example.com/finance-final", "title": "Finance LP"},
    }

    session.add_all([
        _mk_ad(
            "a102_dup_1",
            platform=AdPlatformEnum.FACEBOOK,
            category=AdCategoryEnum.BEAUTY,
            title="dup creative",
            image_url="https://example.com/dup.jpg",
            image_s3_key="images/dup1.jpg",
            destination_url="https://example.com/dup",
            metadata={"last_crawl_keyword": "beauty", "lp_data": {"final_url": "https://example.com/dup"}},
            updated_at=datetime(2026, 3, 8, 10, tzinfo=timezone.utc),
        ),
        _mk_ad(
            "a102_dup_2",
            platform=AdPlatformEnum.FACEBOOK,
            category=AdCategoryEnum.BEAUTY,
            title="dup creative",
            image_url="https://example.com/dup.jpg",
            image_s3_key="images/dup2.jpg",
            destination_url="https://example.com/dup",
            metadata={"last_crawl_keyword": "beauty", "lp_data": {"final_url": "https://example.com/dup"}},
            updated_at=datetime(2026, 3, 8, 11, tzinfo=timezone.utc),
        ),
        _mk_ad(
            "a105_stale",
            platform=AdPlatformEnum.FACEBOOK,
            category=AdCategoryEnum.BEAUTY,
            title="stale creative",
            metadata={"last_crawl_keyword": "sleep", "is_still_running": False},
            updated_at=datetime(2026, 2, 20, 10, tzinfo=timezone.utc),
        ),
    ])
    session.commit()

    stale_ad = session.query(Ad).filter(Ad.external_id == "a105_stale").one()
    stale_ad.first_seen_at = datetime(2026, 2, 20, 10, tzinfo=timezone.utc)
    stale_ad.last_seen_at = datetime(2026, 2, 22, 10, tzinfo=timezone.utc)
    stale_ad.created_at = datetime(2026, 2, 20, 10, tzinfo=timezone.utc)

    for ext_id in ("a102_dup_1", "a102_dup_2"):
        ad = session.query(Ad).filter(Ad.external_id == ext_id).one()
        ad.first_seen_at = datetime(2026, 3, 8, 10, tzinfo=timezone.utc)
        ad.created_at = datetime(2026, 3, 8, 10, tzinfo=timezone.utc)
        ad.last_seen_at = datetime(2026, 3, 8, 10, tzinfo=timezone.utc)

    regress_ad.first_seen_at = datetime(2026, 3, 7, 8, tzinfo=timezone.utc)
    regress_ad.last_seen_at = datetime(2026, 3, 8, 8, tzinfo=timezone.utc)
    regress_ad.created_at = datetime(2026, 3, 7, 8, tzinfo=timezone.utc)
    recover_ad.first_seen_at = datetime(2026, 3, 7, 9, tzinfo=timezone.utc)
    recover_ad.last_seen_at = datetime(2026, 3, 8, 9, tzinfo=timezone.utc)
    recover_ad.created_at = datetime(2026, 3, 7, 9, tzinfo=timezone.utc)
    session.commit()

    second = build_creative_library_audit(session, target_date=date(2026, 3, 8), persist=True)["creative_library_audit"]

    assert second["creative_library_daily_report"]["top_regressions"][0]["ad_id"] == regress_ad.id
    assert second["creative_library_daily_report"]["top_recoveries"][0]["ad_id"] == recover_ad.id
    assert second["live_ingestion_audit"]["daily_new_ads"] == 2
    assert second["live_ingestion_audit"]["daily_unique_ads"] == 1
    assert second["live_ingestion_audit"]["duplicate_rate"] == pytest.approx(0.5, rel=1e-4)
    assert second["live_ingestion_audit"]["stale_ad_rate"] > 0
    assert any(item["keyword"] == "sleep" for item in second["live_ingestion_audit"]["inactive_keywords_7d"])
    assert second["slo_status"]["overall_status"] in {"warning", "critical"}
    assert len(second["ops_alert_candidates"]) >= 1
