from app.services.crawling.base_crawler import CrawledAd
from app.services.crawling.meta_crawler import MetaAdLibraryCrawler, _classify_meta_failure


def test_d106_classify_meta_failure_maps_known_cases():
    assert _classify_meta_failure("403 Client challenge") == "client_challenge"
    assert _classify_meta_failure("Execution context was destroyed") == "execution_context_destroyed"
    assert _classify_meta_failure(status_code=401) == "token_expired"


async def _fake_browser_results():
    ad = CrawledAd(
        external_id="browser-1",
        platform="facebook",
        title="browser fallback ad",
        metadata={"source": "browser_scraping", "creative_source": "browser", "lp_source": "missing"},
    )
    return [ad]


def test_d106_search_ads_propagates_api_failure_reason_to_browser_results(monkeypatch):
    crawler = MetaAdLibraryCrawler(access_token="token")

    async def _fake_api(*_args, **_kwargs):
        crawler._last_search_diagnostics["api_attempted"] = True
        crawler._last_search_diagnostics["api_status"] = "failed"
        crawler._last_search_diagnostics["api_failure_reason"] = "client_challenge"
        return []

    async def _fake_browser(*_args, **_kwargs):
        crawler._last_search_diagnostics["browser_attempted"] = True
        crawler._last_search_diagnostics["browser_status"] = "success"
        crawler._last_search_diagnostics["browser_result_count"] = 1
        return await _fake_browser_results()

    async def _passthrough_enrich(ads):
        return ads

    monkeypatch.setattr(crawler, "_search_via_api", _fake_api)
    monkeypatch.setattr(crawler, "_search_via_browser", _fake_browser)
    monkeypatch.setattr(crawler, "enrich_ads_with_page_metrics", _passthrough_enrich)

    results = __import__("asyncio").run(crawler.search_ads("医療ダイエット", limit=5, enrich_metrics=False))

    assert len(results) == 1
    meta = results[0].metadata
    assert meta["meta_api_failure_reason"] == "client_challenge"
    assert meta["meta_recovery_reason"] == "client_challenge"
    assert meta["meta_recovery_source"] == "browser_fallback"


def test_d106_parse_api_ad_sets_last_meta_success_at():
    crawler = MetaAdLibraryCrawler(access_token="token")
    ad = crawler._parse_api_ad(
        {
            "id": "999",
            "ad_delivery_start_time": "2026-03-07T00:00:00+0000",
            "ad_creative_bodies": ["日本語広告"],
            "ad_creative_link_titles": ["タイトル"],
            "ad_creative_link_thumbnails": ["https://cdn.example.com/thumb.jpg"],
            "publisher_platforms": ["facebook"],
            "page_name": "広告主",
            "impressions": {"lower_bound": "100", "upper_bound": "200"},
            "spend": {"lower_bound": "1000", "upper_bound": "2000"},
            "ad_snapshot_url": "https://www.facebook.com/ads/archive/render_ad/?id=999",
        }
    )

    assert ad is not None
    assert ad.metadata["metric_source"] == "api"
    assert ad.metadata["last_meta_success_at"]
