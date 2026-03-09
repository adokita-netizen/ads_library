from datetime import datetime, timezone

from app.services.crawling.base_crawler import CrawledAd
from app.services.crawling.meta_crawler import (
    MetaAdLibraryCrawler,
    _detail_page_candidates,
    _estimate_ad_metrics,
)


def test_meta_api_parse_sets_provenance_fields():
    crawler = MetaAdLibraryCrawler(access_token="test-token")

    ad = crawler._parse_api_ad(
        {
            "id": "123",
            "ad_delivery_start_time": "2026-03-07T00:00:00+0000",
            "ad_creative_bodies": ["日本語の広告本文です"],
            "ad_creative_link_titles": ["広告タイトル"],
            "ad_creative_link_thumbnails": ["https://cdn.example.com/thumb.jpg"],
            "publisher_platforms": ["facebook", "instagram"],
            "page_id": "42",
            "page_name": "テスト広告主",
            "languages": ["ja"],
            "impressions": {"lower_bound": "100", "upper_bound": "300"},
            "spend": {"lower_bound": "1000", "upper_bound": "2000"},
            "ad_snapshot_url": "https://www.facebook.com/ads/archive/render_ad/?id=123",
        }
    )

    assert ad is not None
    assert ad.metadata["metric_source"] == "api"
    assert ad.metadata["creative_source"] == "api"
    assert ad.metadata["lp_source"] == "missing"
    assert ad.metadata["meta_quality_state"] == "real"


def test_meta_estimated_metrics_mark_estimated_quality():
    ad = CrawledAd(
        external_id="est-1",
        platform="facebook",
        first_seen_at=datetime(2026, 3, 1, tzinfo=timezone.utc),
        metadata={"source": "api"},
    )

    _estimate_ad_metrics(ad)

    assert ad.metadata["metric_source"] == "estimated"
    assert ad.metadata["metrics_estimated"] is True
    assert ad.metadata["meta_quality_state"] == "estimated"


def test_meta_detail_page_candidates_prioritize_render_ad():
    ad = CrawledAd(
        external_id="12345",
        platform="facebook",
        snapshot_url="https://www.facebook.com/ads/library/?id=12345",
    )

    candidates = _detail_page_candidates(ad, "token-123")

    assert candidates[0].startswith("https://www.facebook.com/ads/archive/render_ad/")
    assert "access_token=token-123" in candidates[0]
    assert candidates[-1] == "https://www.facebook.com/ads/library/?id=12345"
