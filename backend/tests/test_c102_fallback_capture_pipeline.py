import asyncio
import importlib

from app.models.ad import MediaExtractionStatus
from app.services.lp_analysis.lp_crawler import CrawledLP, LPCrawler
from app.tasks import media_tasks
from tests.test_c101_creative_lp_completion_pipeline import _mk_ad


def test_c102_media_task_persists_rendered_screenshot_fallback(session, monkeypatch, tmp_path):
    ad = _mk_ad(
        external_id="c102_screenshot",
        snapshot_url="https://www.facebook.com/ads/library/?id=123",
        media_extraction_status=MediaExtractionStatus.PENDING_HEAVY,
    )
    session.add(ad)
    session.commit()

    storage_mod = importlib.import_module("app.core.storage")

    class _FakeStorage:
        def upload_bytes(self, key, data, content_type="image/jpeg"):
            return None

    class _FakeExtractor:
        async def extract(self, snapshot_url, use_playwright=True):
            extracted = importlib.import_module("app.services.media_extraction").ExtractedMedia()
            extracted.extraction_method = "playwright"
            extracted.screenshot_bytes = b"jpeg-bytes"
            extracted.screenshot_content_type = "image/jpeg"
            return extracted

    monkeypatch.setattr(storage_mod, "get_storage_client", lambda: _FakeStorage())
    monkeypatch.setattr(media_tasks, "_save_to_local_cache", lambda data, media_type, ad_id: str(tmp_path / f"{ad_id}-{media_type}.jpg"))
    monkeypatch.setattr(importlib.import_module("app.services.media_extraction"), "MediaExtractor", lambda: _FakeExtractor())

    result = media_tasks.extract_media_task.run(ad_id=ad.id, use_playwright=True)

    session.expire_all()
    refreshed = session.get(type(ad), ad.id)
    assert result["status"] == "completed"
    assert refreshed.image_s3_key is not None
    assert refreshed.thumbnail_s3_key is not None
    assert refreshed.media_extraction_status == MediaExtractionStatus.COMPLETED


def test_c102_lp_crawler_falls_back_to_playwright(monkeypatch):
    crawler = LPCrawler()

    class _FailingClient:
        async def get(self, url):
            raise RuntimeError("blocked")

    async def _fake_browser(url):
        return CrawledLP(
            url=url,
            final_url=url,
            domain="example.com",
            status_code=200,
            html_content="<html><title>Browser LP</title><body>LP body</body></html>",
            title="Browser LP",
        )

    monkeypatch.setattr(crawler, "_get_client", lambda: _FailingClient())
    monkeypatch.setattr(crawler, "_crawl_via_playwright", _fake_browser)

    result = asyncio.run(crawler.crawl_lp("https://example.com/lp"))

    assert result is not None
    assert result.title == "Browser LP"


def test_c102_download_thumbnail_task_uses_snapshot_screenshot_fallback(session, monkeypatch, tmp_path):
    ad = _mk_ad(
        external_id="c102_thumb_fallback",
        snapshot_url="https://www.facebook.com/ads/library/?id=456",
        image_url="https://cdn.example.com/blocked.jpg",
        media_extraction_status=MediaExtractionStatus.ENRICHED,
    )
    session.add(ad)
    session.commit()

    storage_mod = importlib.import_module("app.core.storage")

    class _FakeStorage:
        def upload_bytes(self, key, data, content_type="image/jpeg"):
            return None

    monkeypatch.setattr(storage_mod, "get_storage_client", lambda: _FakeStorage())
    monkeypatch.setattr(media_tasks, "_download_sync", lambda url, timeout=15.0: None)
    monkeypatch.setattr(media_tasks, "_save_to_local_cache", lambda data, media_type, ad_id: str(tmp_path / f"{ad_id}-{media_type}.jpg"))
    monkeypatch.setattr(media_tasks, "_capture_snapshot_still_bytes", lambda snapshot_url: (b"jpeg-bytes", "image/jpeg"))

    result = media_tasks.download_thumbnail_task.run(ad_id=ad.id)

    session.expire_all()
    refreshed = session.get(type(ad), ad.id)
    assert result["status"] == "completed"
    assert refreshed.image_s3_key is not None
    assert refreshed.thumbnail_s3_key is not None
    assert refreshed.media_extraction_status == MediaExtractionStatus.COMPLETED
