"""Crawl health monitor.

Checks data freshness, crawl coverage, and error rates to determine
overall crawl health status.

Health levels:
  GREEN:  All good, data fresh (< 3 days old)
  YELLOW: Data 3-7 days old or partial failures
  RED:    Data > 7 days old or major failures

Saves health report to backend/data/crawl_health.json.

Run from the backend directory:
    cd backend
    python scripts/crawl_health_monitor.py
"""

import json
import os
import sys
import logging
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

logger = logging.getLogger(__name__)

# ── Paths ────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
CONFIG_DIR = os.path.join(BASE_DIR, "config")

CRAWL_LOG_FILE = os.path.join(DATA_DIR, "crawl_log.json")
CRAWL_HEALTH_FILE = os.path.join(DATA_DIR, "crawl_health.json")
CRAWL_SCHEDULE_FILE = os.path.join(DATA_DIR, "crawl_schedule.json")
KEYWORDS_FILE = os.path.join(CONFIG_DIR, "crawl_keywords.json")

# Thresholds
YELLOW_DAYS = 3
RED_DAYS = 7
ERROR_RATE_YELLOW = 0.2   # 20% error rate -> yellow
ERROR_RATE_RED = 0.5       # 50% error rate -> red


def check_data_freshness(session) -> dict:
    """Check how old the newest ad data is."""
    from sqlalchemy import func

    result = {
        "status": "GREEN",
        "newest_ad_age_hours": None,
        "newest_ad_date": None,
        "oldest_ad_date": None,
        "total_ads": 0,
    }

    total_ads = session.query(func.count(Ad.id)).scalar() or 0
    result["total_ads"] = total_ads

    if total_ads == 0:
        result["status"] = "RED"
        result["message"] = "No ads in database"
        return result

    # Find newest ad by created_at
    newest = session.query(func.max(Ad.created_at)).scalar()
    oldest = session.query(func.min(Ad.created_at)).scalar()

    if newest:
        # Ensure timezone-aware
        if newest.tzinfo is None:
            newest = newest.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        age = now - newest
        age_hours = age.total_seconds() / 3600
        age_days = age_hours / 24

        result["newest_ad_age_hours"] = round(age_hours, 1)
        result["newest_ad_date"] = newest.isoformat()

        if age_days > RED_DAYS:
            result["status"] = "RED"
            result["message"] = f"Data is {age_days:.1f} days old (> {RED_DAYS} days)"
        elif age_days > YELLOW_DAYS:
            result["status"] = "YELLOW"
            result["message"] = f"Data is {age_days:.1f} days old (> {YELLOW_DAYS} days)"
        else:
            result["message"] = f"Data is {age_hours:.1f} hours old"

    if oldest:
        if oldest.tzinfo is None:
            oldest = oldest.replace(tzinfo=timezone.utc)
        result["oldest_ad_date"] = oldest.isoformat()

    return result


def check_crawl_coverage() -> dict:
    """Check if all configured pages/keywords are being crawled."""
    result = {
        "status": "GREEN",
        "configured_keywords": 0,
        "message": "No keyword config found",
    }

    if not os.path.exists(KEYWORDS_FILE):
        result["status"] = "YELLOW"
        result["message"] = "Keyword config file not found"
        return result

    try:
        with open(KEYWORDS_FILE, "r", encoding="utf-8") as f:
            config = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        result["status"] = "YELLOW"
        result["message"] = f"Cannot read keyword config: {str(e)}"
        return result

    keywords = config.get("keywords", [])
    platforms = config.get("platforms", [])
    result["configured_keywords"] = len(keywords)
    result["configured_platforms"] = platforms

    if len(keywords) == 0:
        result["status"] = "YELLOW"
        result["message"] = "No keywords configured"
    else:
        result["message"] = f"{len(keywords)} keywords on {len(platforms)} platforms"

    return result


def check_error_rates() -> dict:
    """Check error rates from recent crawl logs."""
    result = {
        "status": "GREEN",
        "recent_runs": 0,
        "success_runs": 0,
        "failed_runs": 0,
        "error_rate": 0.0,
        "last_errors": [],
    }

    if not os.path.exists(CRAWL_LOG_FILE):
        result["message"] = "No crawl log found"
        return result

    try:
        with open(CRAWL_LOG_FILE, "r", encoding="utf-8") as f:
            logs = json.load(f)
    except (json.JSONDecodeError, OSError):
        result["status"] = "YELLOW"
        result["message"] = "Cannot read crawl log"
        return result

    if not logs:
        result["message"] = "Crawl log is empty"
        return result

    # Check last 10 runs
    recent = logs[-10:]
    result["recent_runs"] = len(recent)

    for entry in recent:
        if entry.get("success"):
            result["success_runs"] += 1
        else:
            result["failed_runs"] += 1
            error = entry.get("error", "Unknown error")
            result["last_errors"].append({
                "timestamp": entry.get("timestamp_utc", "unknown"),
                "error": error[:200],
            })

    if result["recent_runs"] > 0:
        result["error_rate"] = round(result["failed_runs"] / result["recent_runs"], 2)

    if result["error_rate"] >= ERROR_RATE_RED:
        result["status"] = "RED"
        result["message"] = f"High error rate: {result['error_rate'] * 100:.0f}%"
    elif result["error_rate"] >= ERROR_RATE_YELLOW:
        result["status"] = "YELLOW"
        result["message"] = f"Elevated error rate: {result['error_rate'] * 100:.0f}%"
    else:
        result["message"] = f"Error rate: {result['error_rate'] * 100:.0f}%"

    # Keep only last 5 errors
    result["last_errors"] = result["last_errors"][-5:]

    return result


def check_media_health() -> dict:
    """Quick check of media cache health."""
    result = {
        "status": "GREEN",
        "thumb_files": 0,
        "image_files": 0,
        "video_files": 0,
        "cache_size_mb": 0.0,
    }

    total_bytes = 0

    thumb_dir = os.path.join(CACHE_DIR, "thumbnails")
    if os.path.isdir(thumb_dir):
        files = [f for f in os.listdir(thumb_dir) if f.endswith(".jpg")]
        result["thumb_files"] = len(files)
        for f in files:
            total_bytes += os.path.getsize(os.path.join(thumb_dir, f))

    img_dir = os.path.join(CACHE_DIR, "images")
    if os.path.isdir(img_dir):
        files = [f for f in os.listdir(img_dir) if f.endswith(".jpg")]
        result["image_files"] = len(files)
        for f in files:
            total_bytes += os.path.getsize(os.path.join(img_dir, f))

    vid_dir = os.path.join(CACHE_DIR, "videos")
    if os.path.isdir(vid_dir):
        files = [f for f in os.listdir(vid_dir)
                 if f.endswith((".mp4", ".webm", ".mov"))]
        result["video_files"] = len(files)
        for f in files:
            total_bytes += os.path.getsize(os.path.join(vid_dir, f))

    result["cache_size_mb"] = round(total_bytes / (1024 * 1024), 2)

    total_files = result["thumb_files"] + result["image_files"] + result["video_files"]
    if total_files == 0:
        result["status"] = "RED"
        result["message"] = "No cached media files"
    else:
        result["message"] = f"{total_files} files, {result['cache_size_mb']:.1f} MB"

    return result


def check_schedule_health() -> dict:
    """Check if scheduled crawl is configured and running."""
    result = {
        "status": "GREEN",
        "last_crawl": None,
        "total_runs": 0,
    }

    if not os.path.exists(CRAWL_SCHEDULE_FILE):
        result["status"] = "YELLOW"
        result["message"] = "No schedule configured (run scheduled_crawl_runner.py)"
        return result

    try:
        with open(CRAWL_SCHEDULE_FILE, "r", encoding="utf-8") as f:
            schedule = json.load(f)
    except (json.JSONDecodeError, OSError):
        result["status"] = "YELLOW"
        result["message"] = "Cannot read schedule file"
        return result

    result["last_crawl"] = schedule.get("last_crawl_utc")
    result["total_runs"] = schedule.get("total_runs", 0)

    if not result["last_crawl"]:
        result["status"] = "YELLOW"
        result["message"] = "No crawl has been run yet"
    else:
        result["message"] = f"Last crawl: {result['last_crawl']}, total runs: {result['total_runs']}"

    return result


def determine_overall_status(checks: dict) -> str:
    """Determine overall health status from individual checks."""
    statuses = [c.get("status", "GREEN") for c in checks.values()]

    if "RED" in statuses:
        return "RED"
    elif "YELLOW" in statuses:
        return "YELLOW"
    return "GREEN"


STATUS_INDICATORS = {
    "GREEN": "[OK]",
    "YELLOW": "[WARN]",
    "RED": "[FAIL]",
}


def main():
    print("=" * 60)
    print("  CRAWL HEALTH MONITOR")
    print("=" * 60)
    print()

    os.makedirs(DATA_DIR, exist_ok=True)

    now_utc = datetime.now(timezone.utc)

    session = SyncSessionLocal()
    try:
        # Run all checks
        checks = {}

        print("  Checking data freshness...")
        checks["data_freshness"] = check_data_freshness(session)

        print("  Checking crawl coverage...")
        checks["crawl_coverage"] = check_crawl_coverage()

        print("  Checking error rates...")
        checks["error_rates"] = check_error_rates()

        print("  Checking media health...")
        checks["media_health"] = check_media_health()

        print("  Checking schedule health...")
        checks["schedule_health"] = check_schedule_health()

    finally:
        session.close()

    # Determine overall status
    overall = determine_overall_status(checks)

    # Build report
    health_report = {
        "timestamp_utc": now_utc.isoformat(),
        "overall_status": overall,
        "checks": checks,
    }

    # Save to file
    try:
        with open(CRAWL_HEALTH_FILE, "w", encoding="utf-8") as f:
            json.dump(health_report, f, indent=2, ensure_ascii=True)
        print(f"\n  Report saved to: {CRAWL_HEALTH_FILE}")
    except OSError as e:
        print(f"\n  WARNING: Could not save report: {e}")

    # Print formatted report
    print()
    print("=" * 60)
    print(f"  HEALTH STATUS: {overall} {STATUS_INDICATORS[overall]}")
    print("=" * 60)

    for check_name, check_data in checks.items():
        status = check_data.get("status", "GREEN")
        message = check_data.get("message", "")
        indicator = STATUS_INDICATORS[status]
        label = check_name.replace("_", " ").title()
        print(f"  {indicator} {label}: {message}")

    print()

    # Detail section
    freshness = checks.get("data_freshness", {})
    print(f"  Total ads:       {freshness.get('total_ads', 0)}")
    print(f"  Newest ad:       {freshness.get('newest_ad_date', 'N/A')}")
    print(f"  Data age:        {freshness.get('newest_ad_age_hours', 'N/A')} hours")

    media = checks.get("media_health", {})
    print(f"  Cached media:    {media.get('thumb_files', 0)} thumbs, "
          f"{media.get('image_files', 0)} images, "
          f"{media.get('video_files', 0)} videos")
    print(f"  Cache size:      {media.get('cache_size_mb', 0):.1f} MB")

    errors = checks.get("error_rates", {})
    print(f"  Recent runs:     {errors.get('recent_runs', 0)} "
          f"(success: {errors.get('success_runs', 0)}, failed: {errors.get('failed_runs', 0)})")

    print("=" * 60)


if __name__ == "__main__":
    main()
