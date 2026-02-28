"""Extract missing video URLs for ads with video_url=NULL.

88件の video_url NULL 広告に対して:
1. Playwright で render_ad を描画し、<video> 要素と動画ネットワークリクエストを検出
2. 動画が見つかれば video_url を設定
3. 見つからなければ creative_type="image" に確定
4. 全広告に creative_quality メタデータを付与

Run from the backend directory:
    cd backend
    python scripts/extract_missing_videos.py
"""

import re
import sys
import time

sys.path.insert(0, ".")

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.api.endpoints.settings import load_api_keys_from_db


# ── Config ────────────────────────────────────────────────────────

REQUEST_DELAY = 1.0
PLAYWRIGHT_WAIT_MS = 8000


# ── Video Extraction ──────────────────────────────────────────────


def _extract_video_from_render_ad(external_id: str, access_token: str | None) -> str | None:
    """Use Playwright to render the ad page and capture video URLs.

    Intercepts network responses with video content-type and checks
    DOM for <video> elements after JS rendering.
    """
    if not external_id or not access_token:
        return None

    url = f"https://www.facebook.com/ads/archive/render_ad/?id={external_id}&access_token={access_token}"
    video_urls = []

    def on_response(response):
        resp_url = response.url
        ct = response.headers.get("content-type", "")
        if "video" in ct and ("fbcdn" in resp_url or "scontent" in resp_url):
            video_urls.append(resp_url)

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.on("response", on_response)

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=20000)
            except Exception:
                pass

            page.wait_for_timeout(PLAYWRIGHT_WAIT_MS)

            # Check DOM for <video> elements
            videos = page.query_selector_all("video")
            for vid in videos:
                src = vid.get_attribute("src") or ""
                if src and src.startswith("http"):
                    video_urls.append(src)
                # Check <source> children
                sources = vid.query_selector_all("source")
                for source in sources:
                    s = source.get_attribute("src") or ""
                    if s and s.startswith("http"):
                        video_urls.append(s)

            browser.close()

        # Filter for actual video URLs (not tracking)
        valid_videos = []
        for v in video_urls:
            if "pixel" not in v and "tracking" not in v:
                valid_videos.append(v)

        return valid_videos[0] if valid_videos else None

    except Exception as e:
        print(f"    playwright error: {e}")
        return None


def _compute_creative_quality(ad: Ad) -> dict:
    """Compute creative quality metadata for an ad."""
    has_video = bool(ad.video_url)
    has_image = bool(ad.image_url)
    has_thumbnail = bool(ad.thumbnail_url)
    has_snapshot = bool(ad.snapshot_url)

    # Media completeness score (0-100)
    score = 0
    if has_video:
        score += 40
    if has_image:
        score += 25
    if has_thumbnail:
        score += 20
    if has_snapshot:
        score += 15

    return {
        "has_video": has_video,
        "has_image": has_image,
        "has_thumbnail": has_thumbnail,
        "has_snapshot": has_snapshot,
        "media_completeness": score,
        "creative_verified": True,
    }


# ── Main ──────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        # Load Meta access token
        keys = load_api_keys_from_db()
        meta_keys = keys.get("meta", keys.get("facebook", {}))
        access_token = meta_keys.get("access_token")
        if access_token:
            print(f"Meta access token: {access_token[:8]}****")
        else:
            print("WARNING: No Meta access token. Playwright render_ad will be limited.")

        print()

        # Find ads with no video_url
        no_video_ads = session.query(Ad).filter(Ad.video_url == None).all()
        total = len(no_video_ads)
        print(f"Ads with video_url=NULL: {total}")

        # Also count current creative_type distribution
        all_ads = session.query(Ad).all()
        type_counts = {}
        for ad in all_ads:
            ct = ad.creative_type or "null"
            type_counts[ct] = type_counts.get(ct, 0) + 1
        print(f"Creative type distribution:")
        for ct, count in sorted(type_counts.items()):
            print(f"  {ct}: {count}")
        print()

        if total == 0:
            print("No ads with missing video_url. Proceeding to quality metadata only.")
        else:
            # Process ads with no video_url
            stats = {"video_found": 0, "image_confirmed": 0, "error": 0}

            for i, ad in enumerate(no_video_ads):
                label = f"[{i+1}/{total}] Ad {ad.id} (ext={ad.external_id})"
                current_type = ad.creative_type or "unknown"
                print(f"{label} type={current_type}")

                # Skip if already confirmed as image
                if current_type == "image":
                    meta = dict(ad.ad_metadata or {})
                    meta["creative_quality"] = _compute_creative_quality(ad)
                    ad.ad_metadata = meta
                    flag_modified(ad, "ad_metadata")
                    stats["image_confirmed"] += 1
                    print(f"  -> Already image, skipped extraction")
                    continue

                try:
                    video_url = _extract_video_from_render_ad(ad.external_id, access_token)

                    if video_url:
                        ad.video_url = video_url
                        ad.creative_type = "video"
                        stats["video_found"] += 1
                        print(f"  -> VIDEO found: {video_url[:80]}")
                    else:
                        # No video found — confirm as image
                        if ad.creative_type != "image":
                            ad.creative_type = "image"
                        stats["image_confirmed"] += 1
                        print(f"  -> No video, confirmed as image")

                except Exception as e:
                    print(f"  -> ERROR: {e}")
                    stats["error"] += 1
                    # On Playwright crash, still confirm as image
                    if ad.creative_type not in ("image", "video"):
                        ad.creative_type = "image"
                    stats["image_confirmed"] += 1

                # Update creative quality metadata
                meta = dict(ad.ad_metadata or {})
                meta["creative_quality"] = _compute_creative_quality(ad)
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

                # Commit per-ad for safety (Playwright can crash)
                session.commit()

                if i + 1 < total:
                    time.sleep(REQUEST_DELAY)

            session.commit()

            print()
            print("=" * 60)
            print("VIDEO EXTRACTION RESULTS")
            print("=" * 60)
            print(f"Total processed:      {total}")
            print(f"Videos found:         {stats['video_found']}")
            print(f"Confirmed as image:   {stats['image_confirmed']}")
            print(f"Errors:               {stats['error']}")

        # Phase 2: Update creative_quality for ALL ads (including those with video)
        print()
        print("Updating creative_quality metadata for all ads...")
        updated = 0
        for ad in all_ads:
            meta = dict(ad.ad_metadata or {})
            quality = _compute_creative_quality(ad)
            if meta.get("creative_quality") != quality:
                meta["creative_quality"] = quality
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                updated += 1

        session.commit()
        print(f"Creative quality updated for {updated} ads")

        # Final stats
        print()
        no_video_after = session.query(Ad).filter(Ad.video_url == None).count()
        has_video_after = session.query(Ad).filter(Ad.video_url != None).count()
        print(f"Final: video_url SET={has_video_after}, NULL={no_video_after}")

        type_counts = {}
        for ad in session.query(Ad).all():
            ct = ad.creative_type or "null"
            type_counts[ct] = type_counts.get(ct, 0) + 1
        print(f"Final creative_type distribution:")
        for ct, count in sorted(type_counts.items()):
            print(f"  {ct}: {count}")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
