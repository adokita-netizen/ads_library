import asyncio
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.endpoints import ads, media, rankings
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum
from app.schemas.ad import build_media_status_payload


def _mk_ad(**overrides) -> Ad:
    payload = {
        "external_id": "c96_ad",
        "title": "Creative contract ad",
        "platform": AdPlatformEnum.FACEBOOK,
        "status": AdStatusEnum.PENDING,
        "advertiser_name": "Contract Tester",
        "created_at": datetime(2026, 3, 8, tzinfo=timezone.utc),
        "updated_at": datetime(2026, 3, 8, tzinfo=timezone.utc),
        "ad_metadata": {},
    }
    payload.update(overrides)
    return Ad(**payload)


class _AsyncSessionWrapper:
    def __init__(self, session):
        self._session = session

    async def execute(self, statement):
        return self._session.execute(statement)


def test_c96_media_status_payload_fixed_shape():
    ad = _mk_ad(
        image_url="https://example.com/image.jpg",
        destination_url="https://example.com/lp",
        ad_metadata={"lp_status": "alive"},
    )

    status = build_media_status_payload(ad)

    assert status == {
        "viewable": True,
        "downloadable": False,
        "has_lp": True,
        "primary_type": "image",
        "missing_reasons": ["download_unavailable"],
    }


def test_c96_rankings_fallback_embeds_media_status_dict(session):
    ad = _mk_ad(
        external_id="c96_rankings",
        title="日本向けクリエイティブ",
        description="日本限定の訴求です",
        advertiser_name="契約テスター日本",
        image_url="https://example.com/image.jpg",
        destination_url="https://example.com/lp",
        ad_metadata={"lp_status": "alive", "language": "ja"},
    )
    session.add(ad)
    session.commit()

    result = rankings._fallback_ad_list(session, genre=None, platform=None, page=1, page_size=20, period="weekly")

    item = next(entry for entry in result["items"] if entry["ad_id"] == ad.id)
    assert item["media_status"]["viewable"] is True
    assert item["media_status"]["downloadable"] is False
    assert item["media_status"]["has_lp"] is True
    assert "download_unavailable" in item["media_status"]["missing_reasons"]
    assert item["media_cache_status"] == "uncached"


def test_c96_rankings_fallback_excludes_non_japanese_ads(session):
    jp_ad = _mk_ad(
        external_id="c96_jp_fallback",
        title="日本限定キャンペーン",
        description="初回限定でお届けします",
        advertiser_name="日本テスター",
        ad_metadata={},
    )
    non_jp_ad = _mk_ad(
        external_id="c96_en_fallback",
        title="Our EXCLUSIVE NEW YEAR SALE is finally here",
        description="Shop now",
        advertiser_name="Global Tester",
        ad_metadata={"language": "en"},
    )
    session.add_all([jp_ad, non_jp_ad])
    session.commit()

    result = rankings._fallback_ad_list(session, genre=None, platform=None, page=1, page_size=20, period="weekly")
    ad_ids = {item["ad_id"] for item in result["items"]}

    assert jp_ad.id in ad_ids
    assert non_jp_ad.id not in ad_ids


def test_c96_media_endpoints_return_fixed_error_codes(session, monkeypatch, tmp_path):
    cache_dir = tmp_path / "media_cache"
    monkeypatch.setattr(media, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(media, "DOWNLOAD_DIR", str(cache_dir / "downloads"))
    monkeypatch.setattr(media, "FRAMES_DIR", str(cache_dir / "frames"))

    ad = _mk_ad(
        external_id="c96_media_status",
        image_url="https://example.com/image.jpg",
        destination_url="https://example.com/lp",
        ad_metadata={"lp_status": "alive"},
    )
    session.add(ad)
    session.commit()

    app = FastAPI()
    app.include_router(media.router, prefix="/api/v1")
    client = TestClient(app)

    status_res = client.get(f"/api/v1/media/status/{ad.id}")
    assert status_res.status_code == 200
    status_payload = status_res.json()
    assert status_payload["media_status"] == {
        "viewable": True,
        "downloadable": False,
        "has_lp": True,
        "primary_type": "image",
        "missing_reasons": ["download_unavailable"],
    }
    assert status_payload["lp_info"]["lp_status"] == "alive"
    assert status_payload["lp_info"]["resolved_url"] == "https://example.com/lp"

    invalid_res = client.post("/api/v1/media/bulk-download", json={"ad_ids": []})
    assert invalid_res.status_code == 400
    assert invalid_res.json()["detail"]["failure_reason_code"] == "invalid_ad_ids"

    missing_res = client.post("/api/v1/media/bulk-download", json={"ad_ids": [ad.id]})
    assert missing_res.status_code == 404
    assert missing_res.json()["detail"]["failure_reason_code"] == "no_cached_media"


def test_c99_ads_media_endpoint_returns_normalized_lp_info(session):
    destination_url = "https://example.com/lp"
    resolved_url = "https://lp.example-cdn.com/final"
    ad = _mk_ad(
        external_id="c99_ads_media",
        snapshot_url="https://example.com/snapshot",
        destination_url=destination_url,
        ad_metadata={
            "lp_status": "302",
            "lp_http_status": 302,
            "redirect_chain": [destination_url, resolved_url],
            "lp_final_url": resolved_url,
        },
    )
    session.add(ad)
    session.commit()

    payload = asyncio.run(ads.get_ad_media(ad.id, None, _AsyncSessionWrapper(session)))

    assert payload["download_url"] == f"/api/v1/media/download/{ad.id}"
    assert payload["media_status"] == {
        "viewable": True,
        "downloadable": False,
        "has_lp": True,
        "primary_type": "unknown",
        "missing_reasons": ["snapshot_only", "download_unavailable"],
    }
    assert payload["lp_info"] == {
        "destination_url": destination_url,
        "domain": "example.com",
        "destination_type": "lp",
        "lp_status": "redirect",
        "lp_score": None,
        "has_lp": True,
        "resolved_url": resolved_url,
        "redirect_chain": [destination_url, resolved_url],
        "final_domain": "lp.example-cdn.com",
        "http_status": 302,
    }


def test_c100_bulk_download_contract_exposes_counts_and_skipped_reasons(session, monkeypatch, tmp_path):
    cache_dir = tmp_path / "media_cache"
    monkeypatch.setattr(media, "CACHE_DIR", str(cache_dir))
    monkeypatch.setattr(media, "DOWNLOAD_DIR", str(cache_dir / "downloads"))
    monkeypatch.setattr(media, "FRAMES_DIR", str(cache_dir / "frames"))

    downloadable_ad = _mk_ad(
        external_id="c100_downloadable",
        image_url="https://example.com/image.jpg",
        destination_url="https://example.com/lp",
        ad_metadata={"lp_status": "alive"},
    )
    snapshot_only_ad = _mk_ad(
        external_id="c100_snapshot_only",
        snapshot_url="https://example.com/snapshot",
        destination_url="https://example.com/lp",
        ad_metadata={"lp_status": "unresolved"},
    )
    session.add_all([downloadable_ad, snapshot_only_ad])
    session.commit()

    media_file = tmp_path / "cached-image.jpg"
    media_file.write_bytes(b"jpeg-bytes")

    def _find_best(ad_id: int):
        if ad_id == downloadable_ad.id:
            return str(media_file), "image/jpeg", "image"
        return None

    async def _ensure_cached(_ad_id: int):
        return None

    monkeypatch.setattr(media, "_find_best_creative", _find_best)
    monkeypatch.setattr(media, "_ensure_best_creative_cached", _ensure_cached)

    app = FastAPI()
    app.include_router(media.router, prefix="/api/v1")
    client = TestClient(app)

    response = client.post(
        "/api/v1/media/bulk-download",
        json={"ad_ids": [downloadable_ad.id, snapshot_only_ad.id]},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["requested_count"] == 2
    assert payload["downloaded_count"] == 1
    assert payload["file_count"] == 1
    assert payload["skipped_ids"] == [snapshot_only_ad.id]
    assert payload["skipped_reasons"] == {str(snapshot_only_ad.id): "snapshot_only"}
    assert payload["skipped_reason_code"] == "no_cached_media"
