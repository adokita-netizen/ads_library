"""D96 recovery batch for creative-library media completeness.

Recovery order:
1. Existing S3 key reconciliation
2. Local cache upload
3. Original image/video/thumbnail URL re-fetch
4. Snapshot HTTP extraction
5. Snapshot browser fallback (Playwright)

Run from the backend directory:
    cd backend
    python scripts/backfill_media_urls.py --limit 100
"""

import argparse
import asyncio
import hashlib
import os
import sys
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import parse_qs, urlparse

import httpx

sys.path.insert(0, ".")

from sqlalchemy import create_engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal, is_in_memory_mode
from app.core.storage import get_storage_client
from app.models.ad import Ad, MediaExtractionStatus, normalize_creative_fetch_reason
from app.services.media_extraction import EXTRACTOR_VERSION, MediaExtractor


def _get_session() -> Session:
    """Get a DB session, connecting to vaap_local.db if SQLite fallback is active."""
    if not is_in_memory_mode():
        session = SyncSessionLocal()
        session.expire_on_commit = False
        session.autoflush = False
        return session
    db_path = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")
    if not os.path.exists(db_path):
        raise RuntimeError(f"vaap_local.db not found at {db_path}")
    engine = create_engine(f"sqlite:///{db_path}", echo=False, connect_args={"timeout": 30})
    return sessionmaker(bind=engine, expire_on_commit=False, autoflush=False)()


BATCH_SIZE = 10
REQUEST_DELAY = 0.4
URL_TIMEOUT = 20.0
CACHE_ROOT = os.path.join(os.path.dirname(__file__), "..", "media_cache")
COMMIT_RETRIES = 5
COMMIT_RETRY_DELAY = 1.5
META_CARD_SCREENSHOT_JS = r"""(targetId) => {
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const idElements = [];
    while (walker.nextNode()) {
        if ((walker.currentNode.textContent || '').includes('\u30e9\u30a4\u30d6\u30e9\u30eaID')) {
            idElements.push(walker.currentNode.parentElement);
        }
    }
    for (const el of idElements) {
        let card = el;
        for (let i = 0; i < 15; i++) {
            if (!card || !card.parentElement) break;
            card = card.parentElement;
            const text = card.innerText || '';
            if (text.includes('\u30e9\u30a4\u30d6\u30e9\u30eaID') &&
                text.includes('\u5e83\u544a\u306e\u8a73\u7d30\u3092\u898b\u308b')) {
                break;
            }
        }
        if (!card) continue;
        const text = card.innerText || '';
        const match = text.match(/\u30e9\u30a4\u30d6\u30e9\u30eaID:\s*(\d+)/);
        if (targetId && (!match || String(match[1]) !== String(targetId))) continue;
        const rect = card.getBoundingClientRect();
        return {
            x: Math.max(0, rect.x),
            y: Math.max(0, rect.y),
            width: Math.max(0, rect.width),
            height: Math.max(0, rect.height),
        };
    }
    return null;
}"""


def _compute_completeness_score(ad: Ad) -> int:
    score = 0
    if ad.video_url or ad.video_s3_key or ad.s3_key:
        score += 35
    if ad.image_url or ad.image_s3_key:
        score += 30
    if ad.thumbnail_url or ad.thumbnail_s3_key:
        score += 20
    if ad.snapshot_url:
        score += 10
    if ad.destination_url:
        score += 5
    return min(score, 100)


def _is_downloadable(ad: Ad) -> bool:
    return bool(ad.video_s3_key or ad.s3_key or ad.image_s3_key or ad.thumbnail_s3_key)


def _is_viewable(ad: Ad) -> bool:
    return bool(ad.video_url or ad.image_url or ad.thumbnail_url)


def _has_lp(ad: Ad) -> bool:
    meta = ad.ad_metadata or {}
    lp_info = meta.get("lp_info") if isinstance(meta.get("lp_info"), dict) else {}
    return bool(ad.destination_url or lp_info.get("final_url"))


def _access_tier(ad: Ad) -> str:
    if _is_downloadable(ad):
        return "downloadable_with_lp" if _has_lp(ad) else "downloadable"
    if _is_viewable(ad):
        return "viewable_only"
    if ad.snapshot_url:
        return "snapshot_only"
    return "missing"


def _cache_path(media_type: str, ad_id: int) -> str:
    ext_map = {"images": ".jpg", "thumbnails": ".jpg", "videos": ".mp4"}
    return os.path.normpath(os.path.join(CACHE_ROOT, media_type, f"{ad_id}{ext_map[media_type]}"))


def _extract_snapshot_external_id(ad: Ad) -> str | None:
    if ad.external_id:
        return str(ad.external_id)
    if not ad.snapshot_url:
        return None
    parsed = urlparse(ad.snapshot_url)
    query = parse_qs(parsed.query)
    values = query.get("id") or query.get("ad_id")
    if not values:
        return None
    value = str(values[0]).strip()
    return value or None


def _snapshot_candidates(ad: Ad) -> list[str]:
    candidates: list[str] = []
    external_id = _extract_snapshot_external_id(ad)
    if external_id:
        candidates.append(f"https://www.facebook.com/ads/library/?id={external_id}")
    if ad.snapshot_url:
        candidates.append(ad.snapshot_url)
    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        if candidate and candidate not in seen:
            seen.add(candidate)
            deduped.append(candidate)
    return deduped


def _classify_reason(message: str | None) -> str:
    text = str(message or "").lower()
    if any(token in text for token in ("403", "forbidden", "expired", "signature", "access denied")):
        return "blocked_or_expired"
    if any(token in text for token in ("404", "not found")):
        return "not_found_in_api"
    if any(token in text for token in ("format", "mime", "content-type", "decode")):
        return "format_mismatch"
    if "url missing" in text or "no media" in text:
        return "media_url_missing"
    return "download_failed"


def _looks_meta_protected(url: str | None) -> bool:
    if not url:
        return False
    lowered = str(url).lower()
    return any(token in lowered for token in ("facebook.com/ads/", "facebook.com/ads/library", "fbcdn.net"))


def _record_state(
    ad: Ad,
    *,
    status: str,
    source: str | None = None,
    reason: str | None = None,
    issues: list[str] | None = None,
) -> None:
    meta = dict(ad.ad_metadata or {})
    event_at = datetime.now(timezone.utc).isoformat()
    meta["last_recovery_attempt_at"] = event_at
    meta["media_extraction_status"] = ad.media_extraction_status
    meta["media_completeness_score"] = _compute_completeness_score(ad)
    meta["downloadable"] = _is_downloadable(ad)
    meta["viewable"] = _is_viewable(ad) or bool(ad.snapshot_url)
    meta["has_lp"] = _has_lp(ad)
    meta["media_access_tier"] = _access_tier(ad)
    meta["extractor_version"] = EXTRACTOR_VERSION
    meta["creative_fetch_status"] = status
    if source:
        meta["creative_fetch_source"] = source
        meta["last_recovery_source"] = source
    if reason:
        meta["creative_fetch_reason"] = normalize_creative_fetch_reason(reason)
    elif status == "success":
        meta["creative_fetch_reason"] = None
    if issues is not None:
        meta["media_quality_issues"] = issues
    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")


def _download_bytes(url: str, timeout: float = URL_TIMEOUT) -> bytes | None:
    try:
        with httpx.Client(timeout=timeout, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            content_type = response.headers.get("content-type", "").lower()
            if "text/html" in content_type and "image" not in content_type and "video" not in content_type:
                return None
            return response.content
    except Exception:
        return None


def _upload_bytes(ad: Ad, media_type: str, source_url: str, payload: bytes) -> bool:
    if not payload:
        return False
    storage = get_storage_client()
    url_hash = hashlib.md5(source_url.encode()).hexdigest()[:12]
    if media_type == "video":
        object_key = f"videos/{uuid.uuid4()}_{url_hash}.mp4"
        storage.upload_bytes(object_key, payload, content_type="video/mp4")
        ad.video_s3_key = object_key
        ad.s3_key = object_key
    elif media_type == "image":
        object_key = f"images/{uuid.uuid4()}_{url_hash}.jpg"
        storage.upload_bytes(object_key, payload, content_type="image/jpeg")
        ad.image_s3_key = object_key
        if not ad.thumbnail_s3_key:
            ad.thumbnail_s3_key = object_key
    else:
        object_key = f"thumbnails/{uuid.uuid4()}_{url_hash}.jpg"
        storage.upload_bytes(object_key, payload, content_type="image/jpeg")
        ad.thumbnail_s3_key = object_key
    return True


def _safe_commit(session: Session) -> None:
    last_error = None
    for attempt in range(COMMIT_RETRIES):
        try:
            session.commit()
            return
        except OperationalError as exc:
            last_error = exc
            session.rollback()
            if "database is locked" not in str(exc).lower() or attempt == COMMIT_RETRIES - 1:
                raise
            time.sleep(COMMIT_RETRY_DELAY * (attempt + 1))
    if last_error:
        raise last_error


async def _capture_meta_library_screenshot(url: str, target_external_id: str | None) -> bytes | None:
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-dev-shm-usage", "--disable-gpu"],
        )
        context = None
        page = None
        try:
            context = await browser.new_context(
                viewport={"width": 1920, "height": 1080},
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/124.0.0.0 Safari/537.36"
                ),
                locale="ja-JP",
            )
            page = await context.new_page()
            await page.goto(url, wait_until="load", timeout=90000)
            await page.wait_for_timeout(5000)
            for _ in range(2):
                await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                await page.wait_for_timeout(1500)
            clip = await page.evaluate(META_CARD_SCREENSHOT_JS, target_external_id)
            if clip and clip.get("width", 0) >= 200 and clip.get("height", 0) >= 200:
                return await page.screenshot(clip=clip, type="jpeg", quality=85)
            return await page.screenshot(full_page=False, type="jpeg", quality=80)
        except Exception:
            return None
        finally:
            if page:
                await page.close()
            if context:
                await context.close()
            await browser.close()


def _get_ad(session: Session, ad_id: int) -> Ad | None:
    return session.get(Ad, ad_id)


def _candidate_priority(ad: Ad) -> tuple[int, int]:
    meta = ad.ad_metadata or {}
    tier = meta.get("media_access_tier") or _access_tier(ad)
    reason = meta.get("creative_fetch_reason")
    status = str(ad.media_extraction_status.value if hasattr(ad.media_extraction_status, "value") else ad.media_extraction_status)
    if reason == "blocked_or_expired" and tier == "viewable_only":
        return (0, ad.id)
    if tier == "viewable_only":
        return (1, ad.id)
    if tier == "snapshot_only" and status in ("enriched", "pending"):
        return (2, ad.id)
    if reason == "blocked_or_expired" and tier == "snapshot_only":
        return (3, ad.id)
    if tier == "snapshot_only":
        return (4, ad.id)
    return (5, ad.id)


def _phase_candidates(session: Session, limit: int | None) -> list[int]:
    query = session.query(Ad).order_by(Ad.id.asc())
    ads = query.all()
    filtered_ads = [
        ad for ad in ads
        if not _is_downloadable(ad)
        and (ad.snapshot_url or ad.image_url or ad.video_url or ad.thumbnail_url or os.path.exists(_cache_path("images", ad.id))
             or os.path.exists(_cache_path("thumbnails", ad.id)) or os.path.exists(_cache_path("videos", ad.id)))
    ]
    filtered_ads.sort(key=_candidate_priority)
    filtered = [ad.id for ad in filtered_ads]
    if limit:
        return filtered[:limit]
    return filtered


def phase1_reconcile_existing_s3(session: Session, ad_ids: list[int]) -> int:
    print("-- Phase 1: reconcile existing S3 keys --------------------")
    updated = 0
    for ad_id in ad_ids:
        ad = _get_ad(session, ad_id)
        if ad is None:
            continue
        changed = False
        if ad.video_s3_key and not ad.s3_key:
            ad.s3_key = ad.video_s3_key
            changed = True
        if ad.image_s3_key and not ad.thumbnail_s3_key:
            ad.thumbnail_s3_key = ad.image_s3_key
            changed = True
        if changed:
            ad.media_extraction_status = MediaExtractionStatus.COMPLETED
            _record_state(ad, status="success", source="existing_s3")
            updated += 1
    _safe_commit(session)
    print(f"  Reconciled: {updated}")
    return updated


def phase2_restore_local_cache(session: Session, ad_ids: list[int]) -> int:
    print("-- Phase 2: upload local cache ----------------------------")
    recovered = 0
    for index, ad_id in enumerate(ad_ids):
        ad = _get_ad(session, ad_id)
        if ad is None:
            continue
        if _is_downloadable(ad):
            continue

        restored = False
        cache_jobs = [
            ("video", _cache_path("videos", ad.id), ad.video_url or f"cache://videos/{ad.id}"),
            ("image", _cache_path("images", ad.id), ad.image_url or f"cache://images/{ad.id}"),
            ("thumbnail", _cache_path("thumbnails", ad.id), ad.thumbnail_url or f"cache://thumbnails/{ad.id}"),
        ]
        for media_type, path, source_url in cache_jobs:
            if not os.path.exists(path):
                continue
            with open(path, "rb") as handle:
                payload = handle.read()
            if _upload_bytes(ad, media_type, source_url, payload):
                restored = True
                if media_type == "thumbnail" and not ad.thumbnail_url:
                    ad.thumbnail_url = source_url if source_url.startswith("http") else ad.thumbnail_url
                if media_type == "image" and not ad.image_url and ad.thumbnail_url and ad.thumbnail_url.startswith("http"):
                    ad.image_url = ad.thumbnail_url
                break

        if restored:
            ad.media_extraction_status = MediaExtractionStatus.COMPLETED
            _record_state(ad, status="success", source="local_cache")
            recovered += 1

        if (index + 1) % BATCH_SIZE == 0:
            _safe_commit(session)

    _safe_commit(session)
    print(f"  Restored from cache: {recovered}")
    return recovered


def phase3_refetch_original_urls(session: Session, ad_ids: list[int]) -> dict[str, int]:
    print("-- Phase 3: re-fetch original media URLs ------------------")
    stats = {"image": 0, "video": 0, "thumbnail": 0, "failed": 0}
    for index, ad_id in enumerate(ad_ids):
        ad = _get_ad(session, ad_id)
        if ad is None:
            continue
        if _is_downloadable(ad):
            continue

        attempts = [
            ("video", ad.video_url),
            ("image", ad.image_url),
            ("thumbnail", ad.thumbnail_url),
        ]
        recovered = False
        for media_type, url in attempts:
            if not url:
                continue
            payload = _download_bytes(url, timeout=60.0 if media_type == "video" else URL_TIMEOUT)
            if not payload:
                continue
            if media_type == "video" and len(payload) >= 100 * 1024 * 1024:
                continue
            if _upload_bytes(ad, media_type, url, payload):
                recovered = True
                stats[media_type] += 1
                break

        if recovered:
            ad.media_extraction_status = MediaExtractionStatus.COMPLETED
            _record_state(ad, status="success", source="original_url")
        else:
            protected_failure = any(_looks_meta_protected(url) for _, url in attempts if url)
            _record_state(
                ad,
                status="partial" if _is_viewable(ad) else "failed",
                source="original_url",
                reason="blocked_or_expired" if protected_failure else "download_failed",
            )
            stats["failed"] += 1

        if (index + 1) % BATCH_SIZE == 0:
            _safe_commit(session)
        time.sleep(REQUEST_DELAY)

    _safe_commit(session)
    print(f"  image={stats['image']} video={stats['video']} thumbnail={stats['thumbnail']} failed={stats['failed']}")
    return stats


def _apply_extracted_media(ad: Ad, extracted) -> bool:
    changed = False
    if extracted.image_urls and not ad.image_url:
        ad.image_url = extracted.image_urls[0]
        changed = True
    if extracted.video_urls and not ad.video_url:
        ad.video_url = extracted.video_urls[0]
        changed = True
    if extracted.thumbnail_url and not ad.thumbnail_url:
        ad.thumbnail_url = extracted.thumbnail_url
        changed = True
    if extracted.creative_type and extracted.creative_type != "unknown" and ad.creative_type != extracted.creative_type:
        ad.creative_type = extracted.creative_type
        changed = True
    if extracted.destination_url and not ad.destination_url:
        ad.destination_url = extracted.destination_url
        changed = True
    return changed


def phase4_snapshot_extract(session: Session, ad_ids: list[int], *, use_playwright: bool, phase_name: str) -> dict[str, int]:
    print(f"-- {phase_name} --------------------------------")
    stats = {"recovered": 0, "partial": 0, "failed": 0}
    extractor = MediaExtractor(timeout=20.0)

    for index, ad_id in enumerate(ad_ids):
        ad = _get_ad(session, ad_id)
        if ad is None:
            continue
        if _is_downloadable(ad) or not ad.snapshot_url:
            continue

        extracted = None
        last_error = None
        used_snapshot_url = None
        for candidate_url in _snapshot_candidates(ad):
            try:
                attempted = asyncio.run(extractor.extract(candidate_url, use_playwright=use_playwright))
            except Exception as exc:
                last_error = exc
                continue
            if attempted.image_urls or attempted.video_urls or attempted.thumbnail_url:
                extracted = attempted
                used_snapshot_url = candidate_url
                break
            if extracted is None:
                extracted = attempted
                used_snapshot_url = candidate_url

        candidate_urls = _snapshot_candidates(ad)
        blocked_reason = (
            "blocked_or_expired"
            if any(_looks_meta_protected(url) for url in candidate_urls)
            else _classify_reason(last_error)
        )

        if extracted is None:
            _record_state(ad, status="failed", source="browser_fallback" if use_playwright else "snapshot_extract", reason=blocked_reason)
            stats["failed"] += 1
            continue

        changed = _apply_extracted_media(ad, extracted)
        if used_snapshot_url and used_snapshot_url != ad.snapshot_url:
            ad.snapshot_url = used_snapshot_url
            changed = True
        if ad.video_url:
            payload = _download_bytes(ad.video_url, timeout=60.0)
            if payload and len(payload) < 100 * 1024 * 1024:
                _upload_bytes(ad, "video", ad.video_url, payload)
        if not _is_downloadable(ad) and ad.image_url:
            payload = _download_bytes(ad.image_url)
            if payload:
                _upload_bytes(ad, "image", ad.image_url, payload)
        if not _is_downloadable(ad) and ad.thumbnail_url:
            payload = _download_bytes(ad.thumbnail_url)
            if payload:
                _upload_bytes(ad, "thumbnail", ad.thumbnail_url, payload)

        if _is_downloadable(ad):
            ad.media_extraction_status = MediaExtractionStatus.COMPLETED
            _record_state(
                ad,
                status="success",
                source=getattr(extracted, "extraction_method", "") or ("browser_fallback" if use_playwright else "snapshot_extract"),
            )
            stats["recovered"] += 1
        elif changed or _is_viewable(ad):
            if use_playwright and not _is_downloadable(ad):
                screenshot_bytes = asyncio.run(
                    _capture_meta_library_screenshot(
                        used_snapshot_url or ad.snapshot_url,
                        _extract_snapshot_external_id(ad),
                    )
                )
                if screenshot_bytes:
                    screenshot_source = used_snapshot_url or ad.snapshot_url or f"screenshot://{ad.id}"
                    _upload_bytes(ad, "image", screenshot_source, screenshot_bytes)
                    ad.media_extraction_status = MediaExtractionStatus.COMPLETED
                    _record_state(
                        ad,
                        status="success",
                        source="browser_screenshot_fallback",
                    )
                    stats["recovered"] += 1
                    continue
            ad.media_extraction_status = MediaExtractionStatus.ENRICHED
            _record_state(
                ad,
                status="partial",
                source=getattr(extracted, "extraction_method", "") or ("browser_fallback" if use_playwright else "snapshot_extract"),
                reason=blocked_reason,
            )
            stats["partial"] += 1
        else:
            ad.media_extraction_status = MediaExtractionStatus.PENDING_HEAVY if ad.snapshot_url else MediaExtractionStatus.FAILED
            _record_state(
                ad,
                status="failed",
                source=getattr(extracted, "extraction_method", "") or ("browser_fallback" if use_playwright else "snapshot_extract"),
                reason=blocked_reason if blocked_reason != "download_failed" else "media_url_missing",
                issues=["snapshot_only"] if ad.snapshot_url else ["media_missing"],
            )
            stats["failed"] += 1

        if (index + 1) % BATCH_SIZE == 0:
            _safe_commit(session)
        time.sleep(REQUEST_DELAY)

    _safe_commit(session)
    print(f"  recovered={stats['recovered']} partial={stats['partial']} failed={stats['failed']}")
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="D96 creative-library recovery batch")
    parser.add_argument("--limit", type=int, default=100, help="Maximum number of non-downloadable ads to process")
    parser.add_argument("--skip-browser-fallback", action="store_true", help="Skip Playwright fallback phase")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    session = _get_session()
    try:
        candidates = _phase_candidates(session, args.limit)
        print(f"Candidates: {len(candidates)}")
        if not candidates:
            print("No recovery candidates found.")
            return

        phase1_reconcile_existing_s3(session, candidates)
        phase2_restore_local_cache(session, candidates)
        phase3_refetch_original_urls(session, candidates)
        phase4_snapshot_extract(session, candidates, use_playwright=False, phase_name="Phase 4: snapshot extraction")
        if not args.skip_browser_fallback:
            phase4_snapshot_extract(session, candidates, use_playwright=True, phase_name="Phase 5: browser fallback")

        final_ads = [ad for ad_id in candidates if (ad := _get_ad(session, ad_id)) is not None]
        completed = sum(1 for ad in final_ads if _is_downloadable(ad))
        snapshot_only = sum(1 for ad in final_ads if _access_tier(ad) == "snapshot_only")
        viewable_only = sum(1 for ad in final_ads if _access_tier(ad) == "viewable_only")
        print()
        print("-- Summary -----------------------------------------------")
        print(f"downloadable: {completed}/{len(final_ads)}")
        print(f"viewable_only: {viewable_only}")
        print(f"snapshot_only: {snapshot_only}")

    except Exception as exc:
        session.rollback()
        print(f"FATAL ERROR: {exc}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
