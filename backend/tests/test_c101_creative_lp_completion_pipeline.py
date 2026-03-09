from datetime import datetime, timezone
import hashlib
import importlib

from app.models.landing_page import LPAnalysis
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum, MediaExtractionStatus
from app.models.landing_page import LandingPage
from app.tasks import crawl_tasks, lp_tasks, media_tasks
from scripts import recover_creative_lp_completeness


def _mk_ad(**overrides) -> Ad:
    payload = {
        "external_id": "c101_ad",
        "title": "Completion audit ad",
        "platform": AdPlatformEnum.FACEBOOK,
        "status": AdStatusEnum.PENDING,
        "advertiser_name": "Completion Tester",
        "created_at": datetime(2026, 3, 9, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 9, tzinfo=timezone.utc),
        "ad_metadata": {},
    }
    payload.update(overrides)
    return Ad(**payload)


def test_c101_lp_success_sync_persists_lp_content(session, monkeypatch, tmp_path):
    ad = _mk_ad(
        external_id="c101_lp_sync",
        destination_url="https://example.com/start",
    )
    session.add(ad)
    session.commit()

    monkeypatch.setattr(lp_tasks, "_LP_HTML_CACHE_DIR", str(tmp_path))

    lp = LandingPage(
        url=ad.destination_url,
        url_hash="hash-1",
        final_url="https://example.com/final",
        domain="example.com",
        title="Landing page title",
        meta_description="Landing page description",
        og_image_url="https://example.com/og.png",
        word_count=321,
        image_count=4,
        total_sections=6,
        full_text_content="Hero copy\nBody copy\nCTA copy",
        hero_headline="Hero copy",
        primary_cta_text="今すぐ申し込む",
        has_pricing=True,
        price_text="初回980円",
        lp_metadata={"canonical": "https://example.com/canonical", "lang": "ja"},
    )
    html_path = lp_tasks._save_lp_html_cache(ad.id, "<html lang='ja'><title>x</title><body>LP</body></html>")
    crawled = type(
        "Crawled",
        (),
        {
            "final_url": "https://example.com/final",
            "status_code": 200,
            "redirect_chain": ["https://example.com/start", "https://example.com/final"],
        },
    )()

    lp_tasks._sync_lp_success_to_ad(
        session,
        ad_id=ad.id,
        url=ad.destination_url,
        crawled=crawled,
        lp=lp,
        html_path=html_path,
    )

    refreshed = session.get(Ad, ad.id)
    meta = refreshed.ad_metadata
    assert meta["lp_info"]["final_url"] == "https://example.com/final"
    assert meta["lp_info"]["title"] == "Landing page title"
    assert meta["lp_data"]["full_text_content"] == "Hero copy\nBody copy\nCTA copy"
    assert meta["lp_data"]["html_path"] == html_path
    assert meta["lp_status"] == "200"


def test_c101_download_thumbnail_task_uses_image_url_fallback(session, monkeypatch, tmp_path):
    ad = _mk_ad(
        external_id="c101_thumb",
        image_url="https://cdn.example.com/creative.jpg",
        media_extraction_status=MediaExtractionStatus.ENRICHED,
    )
    session.add(ad)
    session.commit()

    monkeypatch.setattr(media_tasks, "_download_sync", lambda url, timeout=15.0: b"jpeg-bytes")
    monkeypatch.setattr(media_tasks, "_save_to_local_cache", lambda data, media_type, ad_id: str(tmp_path / f"{ad_id}-{media_type}.jpg"))

    storage_mod = importlib.import_module("app.core.storage")

    class _FakeStorage:
        def upload_bytes(self, key, data, content_type="image/jpeg"):
            return None

    monkeypatch.setattr(storage_mod, "get_storage_client", lambda: _FakeStorage())

    result = media_tasks.download_thumbnail_task.run(ad_id=ad.id)

    session.expire_all()
    refreshed = session.get(Ad, ad.id)
    assert result["status"] == "completed"
    assert refreshed.thumbnail_s3_key is not None
    assert refreshed.image_s3_key is not None
    assert refreshed.media_extraction_status == MediaExtractionStatus.COMPLETED


def test_c101_needs_lp_enrichment_requires_real_lp_content():
    incomplete_ad = _mk_ad(
        external_id="c101_lp_incomplete",
        destination_url="https://example.com/start",
        ad_metadata={},
    )
    complete_ad = _mk_ad(
        external_id="c101_lp_complete",
        destination_url="https://example.com/start",
        ad_metadata={
            "lp_info": {"final_url": "https://example.com/final", "title": "LP"},
            "lp_data": {"full_text_content": "Long LP body"},
        },
    )

    assert crawl_tasks._needs_lp_enrichment(incomplete_ad) is True
    assert crawl_tasks._needs_lp_enrichment(complete_ad) is False


def test_c101_reuse_existing_lp_for_ad_syncs_completed_lp(session):
    source_ad = _mk_ad(
        external_id="c101_lp_source",
        destination_url="https://example.com/start",
    )
    target_ad = _mk_ad(
        external_id="c101_lp_target",
        destination_url="https://example.com/start",
    )
    session.add_all([source_ad, target_ad])
    session.commit()

    lp = LandingPage(
        ad_id=source_ad.id,
        url=source_ad.destination_url,
        url_hash=hashlib.sha256(source_ad.destination_url.encode()).hexdigest(),
        final_url="https://example.com/final",
        domain="example.com",
        title="Reusable LP",
        meta_description="Reusable description",
        og_image_url="https://example.com/og.png",
        full_text_content="Reusable LP body",
        hero_headline="Reusable hero",
        primary_cta_text="Try now",
        lp_metadata={"canonical": "https://example.com/final", "lang": "ja", "http_status": 200},
    )
    session.add(lp)
    session.commit()

    session.add(LPAnalysis(
        landing_page_id=lp.id,
        overall_quality_score=88.0,
        conversion_potential_score=77.0,
        trust_score=70.0,
        urgency_score=40.0,
    ))
    session.commit()

    assert lp_tasks.reuse_existing_lp_for_ad(session, ad_id=target_ad.id, url=target_ad.destination_url) is True

    refreshed = session.get(Ad, target_ad.id)
    assert refreshed.ad_metadata["lp_data"]["full_text_content"] == "Reusable LP body"
    assert refreshed.ad_metadata["lp_info"]["final_url"] == "https://example.com/final"
    assert refreshed.ad_metadata["lp_analysis"]["quality_score"] == 88.0


def test_c101_recover_lp_content_reuses_one_crawl_for_duplicate_urls(session, monkeypatch):
    ads = [
        _mk_ad(external_id="c101_lp_dupe_1", destination_url="https://example.com/start"),
        _mk_ad(external_id="c101_lp_dupe_2", destination_url="https://example.com/start"),
        _mk_ad(external_id="c101_lp_dupe_3", destination_url="https://example.com/start"),
    ]
    session.add_all(ads)
    session.commit()

    called = {"count": 0}

    def _fake_run(**kwargs):
        called["count"] += 1
        lp = LandingPage(
            ad_id=kwargs["ad_id"],
            url=kwargs["url"],
            url_hash=hashlib.sha256(kwargs["url"].encode()).hexdigest(),
            final_url="https://example.com/final",
            domain="example.com",
            title="Recovered LP",
            full_text_content="Recovered content",
            lp_metadata={"http_status": 200},
        )
        session.add(lp)
        session.commit()
        lp_tasks.reuse_existing_lp_for_ad(session, ad_id=kwargs["ad_id"], url=kwargs["url"])
        return {"status": "completed", "lp_id": lp.id}

    monkeypatch.setattr(lp_tasks.crawl_and_analyze_lp_task, "run", _fake_run)

    result = recover_creative_lp_completeness._recover_lp_content(session, limit=10, auto_analyze=False)

    session.expire_all()
    assert called["count"] == 1
    assert result["completed"] == 3
    for ad in ads:
        refreshed = session.get(Ad, ad.id)
        assert refreshed.ad_metadata["lp_data"]["full_text_content"] == "Recovered content"


def test_c101_lp_failure_sync_persists_terminal_lp_state(session):
    ad = _mk_ad(
        external_id="c101_lp_failure",
        destination_url="https://unreachable.example.com",
    )
    session.add(ad)
    session.commit()

    lp_tasks._sync_lp_failure_to_ad(
        session,
        ad_id=ad.id,
        url=ad.destination_url,
        status="unreachable",
        error_code="unknown",
        error_message="DNS lookup failed",
    )

    refreshed = session.get(Ad, ad.id)
    assert refreshed.ad_metadata["lp_terminal"] is True
    assert refreshed.ad_metadata["lp_data"]["full_text_content"].startswith("Terminal LP state:")
    assert refreshed.ad_metadata["lp_info"]["final_url"] == "https://unreachable.example.com"


def test_c101_recover_missing_destination_terminal_marks_ads_complete(session):
    ad = _mk_ad(
        external_id="c101_no_destination",
        destination_url=None,
    )
    session.add(ad)
    session.commit()

    result = recover_creative_lp_completeness._recover_missing_destination_terminal(session, limit=10)

    session.expire_all()
    refreshed = session.get(Ad, ad.id)
    assert result["completed"] >= 1
    assert ad.id in result["ids"]
    assert refreshed.ad_metadata["lp_terminal"] is True
    assert refreshed.ad_metadata["lp_data"]["terminal_state"] is True
    assert refreshed.ad_metadata["lp_data"]["full_text_content"].startswith("Terminal LP state:")
