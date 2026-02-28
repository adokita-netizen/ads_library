"""Scheduled crawl runner with full pipeline.

Cron-compatible script that:
  1. Checks last crawl timestamp from backend/data/crawl_schedule.json
  2. If enough time has passed (configurable, default 24h), runs crawl
  3. After crawl, runs analysis pipeline (classify_fine_genre, extract_product_names, aggregate_metrics)
  4. After analysis, runs media pipeline (validate, auto-cache)
  5. Logs results to backend/data/crawl_log.json

Exit code 0 on success, 1 on failure.

Run from the backend directory:
    cd backend
    python scripts/scheduled_crawl_runner.py
"""

import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Paths ────────────────────────────────────────────────────────────

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPTS_DIR = os.path.join(BASE_DIR, "scripts")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(BASE_DIR, "logs")

SCHEDULE_FILE = os.path.join(DATA_DIR, "crawl_schedule.json")
CRAWL_LOG_FILE = os.path.join(DATA_DIR, "crawl_log.json")

# Default interval in hours
DEFAULT_INTERVAL_HOURS = 24

# ── Logging setup ────────────────────────────────────────────────────

os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

today_str = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
log_file = os.path.join(LOG_DIR, f"crawl_runner_{today_str}.log")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_file, encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger("scheduled_crawl_runner")


# ── Schedule management ──────────────────────────────────────────────

def load_schedule() -> dict:
    """Load crawl schedule from JSON file."""
    if not os.path.exists(SCHEDULE_FILE):
        return {
            "last_crawl_utc": None,
            "interval_hours": DEFAULT_INTERVAL_HOURS,
            "total_runs": 0,
        }
    try:
        with open(SCHEDULE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("Failed to read schedule file: %s", str(e))
        return {
            "last_crawl_utc": None,
            "interval_hours": DEFAULT_INTERVAL_HOURS,
            "total_runs": 0,
        }


def save_schedule(schedule: dict):
    """Save crawl schedule to JSON file."""
    try:
        with open(SCHEDULE_FILE, "w", encoding="utf-8") as f:
            json.dump(schedule, f, indent=2, ensure_ascii=True)
    except OSError as e:
        logger.error("Failed to save schedule: %s", str(e))


def should_run(schedule: dict) -> tuple[bool, str]:
    """Check if enough time has passed since last crawl.

    Returns (should_run, reason).
    """
    last_crawl = schedule.get("last_crawl_utc")
    interval_hours = schedule.get("interval_hours", DEFAULT_INTERVAL_HOURS)

    if not last_crawl:
        return True, "No previous crawl recorded"

    try:
        last_dt = datetime.fromisoformat(last_crawl)
    except (ValueError, TypeError):
        return True, "Invalid last_crawl timestamp"

    now = datetime.now(timezone.utc)
    elapsed_hours = (now - last_dt).total_seconds() / 3600

    if elapsed_hours >= interval_hours:
        return True, f"Elapsed {elapsed_hours:.1f}h >= interval {interval_hours}h"
    else:
        remaining = interval_hours - elapsed_hours
        return False, f"Only {elapsed_hours:.1f}h elapsed, need {interval_hours}h (remaining: {remaining:.1f}h)"


# ── Pipeline steps ───────────────────────────────────────────────────

def run_script(script_name: str) -> dict:
    """Run a script as a subprocess. Returns result dict."""
    script_path = os.path.join(SCRIPTS_DIR, script_name)
    if not os.path.exists(script_path):
        logger.warning("Script not found: %s", script_name)
        return {"status": "skipped", "reason": "script not found"}

    logger.info("Running: %s", script_name)
    start = time.time()

    try:
        result = subprocess.run(
            [sys.executable, script_path],
            capture_output=True,
            text=True,
            timeout=600,
            cwd=BASE_DIR,
            encoding="utf-8",
            errors="replace",
        )
        elapsed = time.time() - start

        # Log stdout (limited)
        if result.stdout:
            for line in result.stdout.strip().split("\n")[-20:]:
                logger.info("  %s: %s", script_name, line)

        if result.returncode == 0:
            logger.info("  %s completed in %.1fs", script_name, elapsed)
            return {"status": "success", "elapsed_sec": round(elapsed, 1)}
        else:
            stderr_msg = (result.stderr or "")[:500]
            logger.warning("  %s failed (exit %d): %s", script_name, result.returncode, stderr_msg)
            return {"status": "failed", "exit_code": result.returncode, "error": stderr_msg}

    except subprocess.TimeoutExpired:
        logger.warning("  %s timed out after 600s", script_name)
        return {"status": "timeout"}
    except Exception as e:
        logger.error("  %s error: %s", script_name, str(e))
        return {"status": "error", "error": str(e)}


def run_crawl_phase() -> dict:
    """Phase 1: Run the main crawl."""
    logger.info("=" * 60)
    logger.info("PHASE 1: CRAWL")
    logger.info("=" * 60)
    return run_script("scheduled_crawl.py")


def run_analysis_phase() -> dict:
    """Phase 2: Run analysis pipeline."""
    logger.info("=" * 60)
    logger.info("PHASE 2: ANALYSIS PIPELINE")
    logger.info("=" * 60)

    results = {}

    # Step 1: Classify fine genres
    results["classify_fine_genre"] = run_script("classify_fine_genre.py")

    # Step 2: Extract product names
    results["extract_product_names"] = run_script("extract_product_names.py")

    # Step 3: Aggregate metrics
    results["aggregate_metrics"] = run_script("aggregate_metrics.py")

    success_count = sum(1 for r in results.values() if r.get("status") == "success")
    total = len(results)
    logger.info("Analysis phase: %d/%d steps succeeded", success_count, total)

    return results


def run_media_phase() -> dict:
    """Phase 3: Run media pipeline."""
    logger.info("=" * 60)
    logger.info("PHASE 3: MEDIA PIPELINE")
    logger.info("=" * 60)

    results = {}

    # Step 1: Validate existing media
    results["validate_media"] = run_script("validate_media_files.py")

    # Step 2: Auto-cache new media
    results["auto_cache"] = run_script("auto_media_cache.py")

    success_count = sum(1 for r in results.values() if r.get("status") == "success")
    total = len(results)
    logger.info("Media phase: %d/%d steps succeeded", success_count, total)

    return results


# ── Logging results ──────────────────────────────────────────────────

def append_crawl_log(log_entry: dict):
    """Append a log entry to the crawl log file."""
    logs = []
    if os.path.exists(CRAWL_LOG_FILE):
        try:
            with open(CRAWL_LOG_FILE, "r", encoding="utf-8") as f:
                logs = json.load(f)
        except (json.JSONDecodeError, OSError):
            logs = []

    logs.append(log_entry)

    # Keep only last 100 entries
    if len(logs) > 100:
        logs = logs[-100:]

    try:
        with open(CRAWL_LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(logs, f, indent=2, ensure_ascii=True)
    except OSError as e:
        logger.error("Failed to save crawl log: %s", str(e))


# ── Main ─────────────────────────────────────────────────────────────

def main():
    start_time = time.time()
    now_utc = datetime.now(timezone.utc)

    print("=" * 60)
    print("  SCHEDULED CRAWL RUNNER")
    print("=" * 60)
    print(f"  Time: {now_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    # Load schedule
    schedule = load_schedule()
    logger.info("Schedule loaded: last_crawl=%s, interval=%dh, total_runs=%d",
                schedule.get("last_crawl_utc", "never"),
                schedule.get("interval_hours", DEFAULT_INTERVAL_HOURS),
                schedule.get("total_runs", 0))

    # Check if we should run
    do_run, reason = should_run(schedule)
    logger.info("Should run: %s (%s)", do_run, reason)

    if not do_run:
        print(f"  SKIPPED: {reason}")
        print(f"  Next run will be allowed after interval elapses.")
        print("=" * 60)
        sys.exit(0)

    # Count ads before
    ads_before = 0
    try:
        from app.core.database import SyncSessionLocal
        from app.models.ad import Ad
        session = SyncSessionLocal()
        ads_before = session.query(Ad).count()
        session.close()
        logger.info("Ads before: %d", ads_before)
    except Exception as e:
        logger.warning("Could not count ads before: %s", str(e))

    # Run pipeline
    log_entry = {
        "timestamp_utc": now_utc.isoformat(),
        "ads_before": ads_before,
        "phases": {},
        "success": False,
    }

    try:
        # Phase 1: Crawl
        crawl_result = run_crawl_phase()
        log_entry["phases"]["crawl"] = crawl_result

        # Brief pause
        time.sleep(3)

        # Phase 2: Analysis
        analysis_result = run_analysis_phase()
        log_entry["phases"]["analysis"] = analysis_result

        # Phase 3: Media
        media_result = run_media_phase()
        log_entry["phases"]["media"] = media_result

        # Count ads after
        ads_after = 0
        try:
            session = SyncSessionLocal()
            ads_after = session.query(Ad).count()
            session.close()
        except Exception:
            pass

        log_entry["ads_after"] = ads_after
        log_entry["new_ads"] = ads_after - ads_before
        log_entry["success"] = True

        # Update schedule
        schedule["last_crawl_utc"] = now_utc.isoformat()
        schedule["total_runs"] = schedule.get("total_runs", 0) + 1
        save_schedule(schedule)

        elapsed = time.time() - start_time
        log_entry["elapsed_sec"] = round(elapsed, 1)

        logger.info("=" * 60)
        logger.info("CRAWL RUNNER COMPLETED")
        logger.info("=" * 60)
        logger.info("  Ads: %d -> %d (new: %d)", ads_before, ads_after, ads_after - ads_before)
        logger.info("  Total time: %.1fs (%.1f min)", elapsed, elapsed / 60)
        logger.info("  Log: %s", log_file)

        print()
        print("=" * 60)
        print("  COMPLETED SUCCESSFULLY")
        print(f"  Ads: {ads_before} -> {ads_after} (new: {ads_after - ads_before})")
        print(f"  Time: {elapsed:.1f}s")
        print("=" * 60)

    except Exception as e:
        log_entry["success"] = False
        log_entry["error"] = str(e)
        logger.error("FATAL ERROR: %s", str(e))
        print(f"  FATAL ERROR: {e}")
        append_crawl_log(log_entry)
        sys.exit(1)

    # Save log entry
    append_crawl_log(log_entry)
    sys.exit(0)


if __name__ == "__main__":
    main()
