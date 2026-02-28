#!/usr/bin/env python3
"""Scheduled crawl automation script.

Reads keyword list from backend/config/crawl_keywords.json, crawls all
keywords across configured platforms, then runs post-crawl media download,
creative analysis, and scoring pipeline.

Results are logged to backend/logs/crawl_YYYYMMDD.log.

Can be run via cron (Linux) or Task Scheduler (Windows):

    cd backend
    python scripts/scheduled_crawl.py

Cron example (daily at 3 AM):
    0 3 * * * cd /path/to/backend && python scripts/scheduled_crawl.py
"""

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests

# ── Paths ──────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG_PATH = os.path.join(BASE_DIR, "config", "crawl_keywords.json")
LOG_DIR = os.path.join(BASE_DIR, "logs")
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")

API_BASE = os.environ.get("VAAP_API_BASE", "http://localhost:8000/api/v1")
CRAWL_ENDPOINT = f"{API_BASE}/ads/crawl"

# ── Logging setup ──────────────────────────────────────────────────────

os.makedirs(LOG_DIR, exist_ok=True)

today_str = datetime.now(timezone.utc).strftime("%Y%m%d")
log_file = os.path.join(LOG_DIR, f"crawl_{today_str}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("scheduled_crawl")


# ── Config loader ──────────────────────────────────────────────────────

def load_config() -> dict:
    """Load crawl configuration from JSON file."""
    if not os.path.exists(CONFIG_PATH):
        logger.error("Config file not found: %s", CONFIG_PATH)
        sys.exit(1)

    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        config = json.load(f)

    required_keys = ["keywords", "platforms", "limit_per_platform"]
    for key in required_keys:
        if key not in config:
            logger.error("Missing required config key: %s", key)
            sys.exit(1)

    logger.info("Config loaded: %d keywords, platforms=%s, limit=%d",
                len(config["keywords"]), config["platforms"],
                config["limit_per_platform"])
    return config


# ── Phase 1: Crawl ────────────────────────────────────────────────────

def run_crawl(config: dict) -> dict:
    """Send crawl requests for all keywords. Returns summary."""
    keywords = config["keywords"]
    platforms = config["platforms"]
    limit = config["limit_per_platform"]

    logger.info("=" * 60)
    logger.info("PHASE 1: SCHEDULED CRAWL")
    logger.info("=" * 60)

    results = {
        "success": 0,
        "failed": 0,
        "skipped": 0,
        "task_ids": [],
        "errors": [],
    }

    for i, keyword in enumerate(keywords):
        kw_label = keyword.encode("unicode_escape").decode("ascii")
        label = f"[{i + 1}/{len(keywords)}]"

        payload = {
            "query": keyword,
            "platforms": platforms,
            "limit_per_platform": limit,
            "auto_analyze": True,
        }

        try:
            logger.info("%s Crawling keyword: %s", label, kw_label)
            resp = requests.post(CRAWL_ENDPOINT, json=payload, timeout=300)

            if resp.status_code == 200:
                data = resp.json()
                task_id = data.get("task_id", "unknown")
                status = data.get("status", "unknown")

                results["task_ids"].append(task_id)

                if status in ("completed", "started"):
                    results["success"] += 1
                    logger.info("  Status: %s | Task: %s", status, task_id[:12])
                else:
                    results["skipped"] += 1
                    logger.info("  Status: %s (skipped)", status)
            else:
                results["failed"] += 1
                err_text = resp.text[:200].encode("unicode_escape").decode("ascii")
                results["errors"].append(f"{kw_label}: HTTP {resp.status_code}")
                logger.warning("  FAILED: HTTP %d - %s", resp.status_code, err_text)

        except requests.exceptions.Timeout:
            results["failed"] += 1
            results["errors"].append(f"{kw_label}: timeout")
            logger.warning("  FAILED: Request timeout")

        except requests.exceptions.ConnectionError:
            results["failed"] += 1
            results["errors"].append(f"{kw_label}: connection error")
            logger.warning("  FAILED: Connection error (is the server running?)")

        except Exception as e:
            results["failed"] += 1
            err_str = str(e).encode("unicode_escape").decode("ascii")
            results["errors"].append(f"{kw_label}: {err_str}")
            logger.warning("  FAILED: %s", err_str)

        # Sleep between keywords to avoid overloading
        if i < len(keywords) - 1:
            time.sleep(2)

    logger.info("Crawl summary: %d success, %d failed, %d skipped",
                results["success"], results["failed"], results["skipped"])
    if results["errors"]:
        for err in results["errors"]:
            logger.warning("  Error: %s", err)

    return results


# ── Phase 2: Media Download ───────────────────────────────────────────

def run_media_download() -> dict:
    """Download media for new ads (thumbnail_s3_key IS NULL)."""
    from sqlalchemy.orm.attributes import flag_modified
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    logger.info("=" * 60)
    logger.info("PHASE 2: MEDIA DOWNLOAD")
    logger.info("=" * 60)

    os.makedirs(THUMB_DIR, exist_ok=True)
    os.makedirs(IMAGE_DIR, exist_ok=True)

    session = SyncSessionLocal()
    stats = {"thumb_ok": 0, "thumb_skip": 0, "img_ok": 0, "img_skip": 0}

    try:
        ads = session.query(Ad).filter(
            Ad.thumbnail_s3_key.is_(None)
        ).order_by(Ad.id).all()

        total = len(ads)
        logger.info("Ads needing media download: %d", total)

        if total == 0:
            logger.info("No new ads need media download.")
            return stats

        for i, ad in enumerate(ads):
            ad_id = ad.id

            # Thumbnail
            thumb_path = os.path.join(THUMB_DIR, f"{ad_id}.jpg")
            if ad.thumbnail_url and not os.path.exists(thumb_path):
                if _download_file(ad.thumbnail_url, thumb_path):
                    ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad_id}.jpg"
                    stats["thumb_ok"] += 1
                else:
                    stats["thumb_skip"] += 1
                time.sleep(0.3)
            elif ad.thumbnail_url and os.path.exists(thumb_path):
                if not ad.thumbnail_s3_key:
                    ad.thumbnail_s3_key = f"media_cache/thumbnails/{ad_id}.jpg"
                stats["thumb_ok"] += 1

            # Image
            img_path = os.path.join(IMAGE_DIR, f"{ad_id}.jpg")
            if ad.image_url and not os.path.exists(img_path):
                if _download_file(ad.image_url, img_path):
                    ad.image_s3_key = f"media_cache/images/{ad_id}.jpg"
                    stats["img_ok"] += 1
                else:
                    stats["img_skip"] += 1
                time.sleep(0.3)
            elif ad.image_url and os.path.exists(img_path):
                if not ad.image_s3_key:
                    ad.image_s3_key = f"media_cache/images/{ad_id}.jpg"
                stats["img_ok"] += 1

            # Update metadata
            if ad.thumbnail_s3_key or ad.image_s3_key:
                meta = dict(ad.ad_metadata or {})
                meta["media_cached"] = True
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")

            if (i + 1) % 20 == 0:
                session.commit()
                logger.info("  Committed batch %d/%d", i + 1, total)

        session.commit()
        logger.info("Thumbnails: %d downloaded, %d failed",
                     stats["thumb_ok"], stats["thumb_skip"])
        logger.info("Images: %d downloaded, %d failed",
                     stats["img_ok"], stats["img_skip"])

    except Exception as e:
        session.rollback()
        err_str = str(e).encode("unicode_escape").decode("ascii")
        logger.error("Error in media download: %s", err_str)
    finally:
        session.close()

    return stats


def _download_file(url: str, dest_path: str) -> bool:
    """Download a single file. Returns True on success."""
    try:
        resp = requests.get(url, timeout=10, stream=True, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        if resp.status_code != 200:
            return False

        with open(dest_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)

        file_size = os.path.getsize(dest_path)
        if file_size < 100:
            os.remove(dest_path)
            return False

        return True
    except Exception:
        return False


# ── Phase 3: Creative Analysis ────────────────────────────────────────

def run_creative_analysis() -> int:
    """Run creative analysis on new ads missing creative_analysis metadata."""
    from sqlalchemy.orm.attributes import flag_modified
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    logger.info("=" * 60)
    logger.info("PHASE 3: CREATIVE ANALYSIS")
    logger.info("=" * 60)

    # Import analyze_ad function
    scripts_dir = os.path.join(BASE_DIR, "scripts")
    sys.path.insert(0, scripts_dir)
    try:
        from analyze_creative_elements import analyze_ad
    except ImportError:
        logger.warning("analyze_creative_elements not found, skipping analysis phase")
        return 0

    session = SyncSessionLocal()
    analyzed = 0

    try:
        all_ads = session.query(Ad).order_by(Ad.id).all()
        candidates = [ad for ad in all_ads
                       if "creative_analysis" not in (ad.ad_metadata or {})]
        total = len(candidates)
        logger.info("Ads needing creative analysis: %d", total)

        if total == 0:
            return 0

        for i, ad in enumerate(candidates):
            try:
                analysis = analyze_ad(ad)
                meta = dict(ad.ad_metadata or {})
                meta["creative_analysis"] = analysis
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                analyzed += 1
            except Exception as e:
                err_str = str(e).encode("unicode_escape").decode("ascii")
                logger.warning("Analysis failed for ad %d: %s", ad.id, err_str)

            if (i + 1) % 20 == 0:
                session.commit()
                logger.info("  Committed batch %d/%d", i + 1, total)

        session.commit()
        logger.info("Analyzed: %d/%d ads", analyzed, total)

    except Exception as e:
        session.rollback()
        err_str = str(e).encode("unicode_escape").decode("ascii")
        logger.error("Error in creative analysis: %s", err_str)
    finally:
        session.close()

    return analyzed


# ── Phase 4: Dedup ────────────────────────────────────────────────────

def run_dedup() -> dict:
    """Run deduplication on crawled ads."""
    logger.info("=" * 60)
    logger.info("PHASE 4: DEDUPLICATION")
    logger.info("=" * 60)

    try:
        # Import and run the dedup script
        scripts_dir = os.path.join(BASE_DIR, "scripts")
        sys.path.insert(0, scripts_dir)

        # Use subprocess to run dedup_crawled_ads.py so it gets its own process
        import subprocess
        result = subprocess.run(
            [sys.executable, os.path.join(scripts_dir, "dedup_crawled_ads.py")],
            capture_output=True,
            text=True,
            timeout=300,
            cwd=BASE_DIR,
        )
        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                logger.info("  dedup: %s", line)
        if result.returncode != 0 and result.stderr:
            logger.warning("  dedup stderr: %s", result.stderr[:500])

        return {"status": "completed", "returncode": result.returncode}

    except FileNotFoundError:
        logger.warning("dedup_crawled_ads.py not found, skipping")
        return {"status": "skipped"}
    except Exception as e:
        logger.error("Dedup failed: %s", str(e))
        return {"status": "failed", "error": str(e)}


# ── Final Report ──────────────────────────────────────────────────────

def print_final_report(crawl_results: dict, media_stats: dict,
                        analyzed_count: int, dedup_result: dict):
    """Log the final summary report."""
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    try:
        total_ads = session.query(Ad).count()
        with_thumb = session.query(Ad).filter(Ad.thumbnail_s3_key.isnot(None)).count()
        with_img = session.query(Ad).filter(Ad.image_s3_key.isnot(None)).count()
        with_video = session.query(Ad).filter(Ad.video_url.isnot(None)).count()
    finally:
        session.close()

    logger.info("=" * 60)
    logger.info("FINAL REPORT")
    logger.info("=" * 60)
    logger.info("Crawl: %d success, %d failed, %d skipped",
                crawl_results["success"], crawl_results["failed"],
                crawl_results["skipped"])
    logger.info("Media: thumbs=%d ok / %d fail, imgs=%d ok / %d fail",
                media_stats.get("thumb_ok", 0), media_stats.get("thumb_skip", 0),
                media_stats.get("img_ok", 0), media_stats.get("img_skip", 0))
    logger.info("Analysis: %d ads analyzed", analyzed_count)
    logger.info("Dedup: %s", dedup_result.get("status", "unknown"))
    logger.info("DB State: total=%d, thumb=%d, img=%d, video=%d",
                total_ads, with_thumb, with_img, with_video)
    logger.info("Log file: %s", log_file)
    logger.info("=" * 60)


# ── Main ──────────────────────────────────────────────────────────────

def main():
    start_time = time.time()
    logger.info("=" * 60)
    logger.info("VAAP SCHEDULED CRAWL - %s",
                datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"))
    logger.info("=" * 60)

    # Load config
    config = load_config()

    # Count ads before
    ads_before = 0
    try:
        from app.core.database import SyncSessionLocal
        from app.models.ad import Ad
        session = SyncSessionLocal()
        ads_before = session.query(Ad).count()
        session.close()
        logger.info("Ads before crawl: %d", ads_before)
    except Exception:
        logger.warning("Could not count ads before crawl")

    # Phase 1: Crawl
    crawl_results = run_crawl(config)

    # Brief pause for async tasks to settle
    logger.info("Waiting 5 seconds for async tasks to settle...")
    time.sleep(5)

    # Count ads after
    try:
        session = SyncSessionLocal()
        ads_after = session.query(Ad).count()
        session.close()
        new_ads = ads_after - ads_before
        logger.info("Ads after crawl: %d (new: %d)", ads_after, new_ads)
    except Exception:
        logger.warning("Could not count ads after crawl")

    # Phase 2: Media download
    media_stats = run_media_download()

    # Phase 3: Creative analysis
    analyzed_count = run_creative_analysis()

    # Phase 4: Dedup
    dedup_result = run_dedup()

    # Final report
    print_final_report(crawl_results, media_stats, analyzed_count, dedup_result)

    elapsed = time.time() - start_time
    logger.info("Total elapsed time: %.1f seconds (%.1f minutes)",
                elapsed, elapsed / 60)


if __name__ == "__main__":
    main()
