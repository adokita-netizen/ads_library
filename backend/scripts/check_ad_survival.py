"""Ad survival check: verify which ads are still running vs stopped.

Two-stage verification:
  Stage 1: Meta Ad Library API (ad_delivery_stop_time)
  Stage 2: snapshot_url HTTP HEAD request (200 = alive, else = dead)

Updates:
  - is_still_running flag in ad_metadata
  - last_checked_at timestamp in ad_metadata
  - days_running calculation
  - longevity_class classification

Run from the backend directory:
    cd backend
    python scripts/check_ad_survival.py
"""

import argparse
import sys
import time

sys.path.insert(0, ".")

import httpx
from datetime import datetime, timezone
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.api.endpoints.settings import load_api_keys_from_db
from app.services.data_quality_report import build_creative_library_audit


# ── Config ────────────────────────────────────────────────────────

GRAPH_API_VERSION = "v25.0"
ADS_ARCHIVE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/ads_archive"
REQUEST_DELAY = 2.0
API_TIMEOUT = 15.0
SNAPSHOT_TIMEOUT = 10.0
PAGE_LIMIT = 25

API_FIELDS = ",".join([
    "id",
    "ad_delivery_start_time",
    "ad_delivery_stop_time",
    "estimated_audience_size",
    "publisher_platforms",
])


# ── API Functions ─────────────────────────────────────────────────


def get_access_token() -> str | None:
    """Get Meta access token. Returns None if not configured."""
    try:
        keys = load_api_keys_from_db()
        meta_keys = keys.get("meta", keys.get("facebook", {}))
        token = meta_keys.get("access_token")
        return token if token else None
    except Exception:
        return None


def fetch_ads_by_page_id(page_id: str, token: str, request_delay: float = REQUEST_DELAY) -> list[dict]:
    """Fetch ads for a page_id from Meta Ad Library API."""
    all_results = []
    params = {
        "access_token": token,
        "search_terms": "",
        "ad_reached_countries": '["JP"]',
        "fields": API_FIELDS,
        "search_page_ids": page_id,
        "limit": PAGE_LIMIT,
    }

    try:
        with httpx.Client(timeout=API_TIMEOUT) as client:
            resp = client.get(ADS_ARCHIVE_URL, params=params)
            if resp.status_code != 200:
                error = resp.json().get("error", {}).get("message", resp.text[:100])
                print(f"    API error for page {page_id}: {error}")
                return []

            data = resp.json()
            all_results.extend(data.get("data", []))

            pages_fetched = 1
            while "paging" in data and "next" in data["paging"] and pages_fetched < 10:
                time.sleep(request_delay)
                next_url = data["paging"]["next"]
                resp = client.get(next_url)
                if resp.status_code != 200:
                    break
                data = resp.json()
                all_results.extend(data.get("data", []))
                pages_fetched += 1

    except Exception as e:
        print(f"    API exception for page {page_id}: {e}")

    return all_results


# ── Snapshot URL Check ───────────────────────────────────────────


def check_snapshot_url(url: str) -> dict:
    """Check if a snapshot_url is still accessible via HTTP HEAD request.

    Returns dict with:
        reachable: bool (True if HTTP 200)
        status_code: int or None
        error: str or None
    """
    if not url:
        return {"reachable": None, "status_code": None, "error": "no_url"}

    try:
        with httpx.Client(
            timeout=SNAPSHOT_TIMEOUT,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AdLibraryBot/1.0)"},
        ) as client:
            resp = client.head(url)
            # Some servers don't support HEAD, fall back to GET
            if resp.status_code == 405:
                resp = client.get(url)
            return {
                "reachable": resp.status_code == 200,
                "status_code": resp.status_code,
                "error": None,
            }
    except httpx.TimeoutException:
        return {"reachable": False, "status_code": None, "error": "timeout"}
    except httpx.ConnectError:
        return {"reachable": False, "status_code": None, "error": "connect_error"}
    except Exception as e:
        return {"reachable": False, "status_code": None, "error": str(e)[:80]}


# ── Survival Check Logic ─────────────────────────────────────────


def check_ad_survival(ad: Ad, api_data: dict) -> dict:
    """Check if an ad is still running based on API data.

    Returns a dict with survival info:
        matched, is_running, days_running, start_time, stop_time
    """
    now = datetime.now(timezone.utc)
    start_str = api_data.get("ad_delivery_start_time")
    stop_str = api_data.get("ad_delivery_stop_time")

    is_running = stop_str is None
    days_running = 0

    if start_str:
        try:
            start_dt = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            if stop_str:
                end_dt = datetime.fromisoformat(stop_str.replace("Z", "+00:00"))
            else:
                end_dt = now
            days_running = max(1, (end_dt - start_dt).days)
        except (ValueError, TypeError):
            days_running = 1

    # Audience data for enrichment
    audience = api_data.get("estimated_audience_size")
    platforms = api_data.get("publisher_platforms")

    return {
        "matched": True,
        "is_running": is_running,
        "days_running": days_running,
        "start_time": start_str,
        "stop_time": stop_str,
        "audience": audience,
        "platforms": platforms,
    }


def classify_longevity(days: int) -> str:
    """Classify ad longevity based on days running."""
    if days >= 90:
        return "long_runner"
    elif days >= 30:
        return "medium_runner"
    elif days >= 7:
        return "short_runner"
    else:
        return "flash"


def update_ad_survival(ad: Ad, survival: dict):
    """Update Ad record with survival check results."""
    now = datetime.now(timezone.utc)
    meta = dict(ad.ad_metadata or {})

    # Update delivery times
    if survival["start_time"]:
        meta["delivery_start_time"] = survival["start_time"]
        if not ad.first_seen_at:
            try:
                ad.first_seen_at = datetime.fromisoformat(
                    survival["start_time"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

    if survival["stop_time"]:
        meta["delivery_stop_time"] = survival["stop_time"]
        try:
            ad.last_seen_at = datetime.fromisoformat(
                survival["stop_time"].replace("Z", "+00:00")
            )
        except (ValueError, TypeError):
            ad.last_seen_at = now
    else:
        ad.last_seen_at = now

    meta["is_still_running"] = survival["is_running"]
    meta["days_running"] = survival["days_running"]
    meta["survival_checked_at"] = now.isoformat()
    meta["last_checked_at"] = now.isoformat()

    # Longevity classification
    meta["longevity_class"] = classify_longevity(survival["days_running"])

    # Update audience/platform data if available
    audience = survival.get("audience")
    if audience and isinstance(audience, dict):
        meta["estimated_audience_min"] = audience.get("lower_bound")
        meta["estimated_audience_max"] = audience.get("upper_bound")

    platforms = survival.get("platforms")
    if platforms and isinstance(platforms, list):
        meta["publisher_platforms"] = platforms

    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")


def update_ad_snapshot_result(ad: Ad, snapshot_result: dict):
    """Update Ad record with snapshot URL check result."""
    now = datetime.now(timezone.utc)
    meta = dict(ad.ad_metadata or {})

    meta["snapshot_check"] = {
        "reachable": snapshot_result["reachable"],
        "status_code": snapshot_result["status_code"],
        "error": snapshot_result["error"],
        "checked_at": now.isoformat(),
    }
    meta["last_checked_at"] = now.isoformat()

    # If snapshot is unreachable and we had no API data, mark as likely stopped
    if snapshot_result["reachable"] is False:
        # Only downgrade if there is no existing API-confirmed running status
        if meta.get("is_still_running") is None:
            meta["is_still_running"] = False
    elif snapshot_result["reachable"] is True:
        # Snapshot reachable confirms ad may still be active
        if meta.get("is_still_running") is None:
            meta["is_still_running"] = True

    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")


# ── Main ──────────────────────────────────────────────────────────


def parse_args():
    parser = argparse.ArgumentParser(description="Check ad survival status (API + snapshot)")
    parser.add_argument("--max-page-ids", type=int, default=None, help="Limit Stage1 page_id checks")
    parser.add_argument("--max-snapshot-checks", type=int, default=None, help="Limit Stage2 snapshot checks")
    parser.add_argument("--max-seconds", type=int, default=None, help="Abort after this many seconds")
    parser.add_argument("--request-delay", type=float, default=REQUEST_DELAY, help="Delay between API requests")
    parser.add_argument("--snapshot-delay", type=float, default=0.5, help="Delay between snapshot checks")
    return parser.parse_args()


def main():
    args = parse_args()
    session = SyncSessionLocal()
    try:
        started = time.monotonic()

        def time_exceeded() -> bool:
            return args.max_seconds is not None and (time.monotonic() - started) >= args.max_seconds

        # Try to get Meta API token (optional)
        token = get_access_token()
        has_api = token is not None
        if has_api:
            print(f"Meta access token: {token[:8]}****")
        else:
            print("No Meta access token configured. Using snapshot_url check only.")
        print()

        # Load all ads
        ads = session.query(Ad).all()
        total_ads = len(ads)
        if total_ads == 0:
            print("No ads found in database. Exiting.")
            return

        # Group ads by page_id (for API check)
        page_id_to_ads: dict[str, list[Ad]] = {}
        no_page_id: list[Ad] = []

        for ad in ads:
            meta = ad.ad_metadata or {}
            page_id = meta.get("page_id")
            if page_id:
                page_id_str = str(page_id)
                if page_id_str not in page_id_to_ads:
                    page_id_to_ads[page_id_str] = []
                page_id_to_ads[page_id_str].append(ad)
            else:
                no_page_id.append(ad)

        page_items = list(page_id_to_ads.items())
        if args.max_page_ids is not None:
            page_items = page_items[: max(0, args.max_page_ids)]

        total_pages = len(page_items)
        print(f"Total ads: {total_ads}")
        print(f"Unique page_ids: {total_pages}")
        print(f"Ads without page_id: {len(no_page_id)}")

        # Show current survival status
        currently_running = sum(
            1 for a in ads
            if (a.ad_metadata or {}).get("is_still_running") is True
        )
        currently_stopped = sum(
            1 for a in ads
            if (a.ad_metadata or {}).get("is_still_running") is False
        )
        unknown = total_ads - currently_running - currently_stopped
        print(f"Current status: running={currently_running}, stopped={currently_stopped}, unknown={unknown}")
        print()

        # Stats tracker
        stats = {
            "api_calls": 0,
            "api_matched": 0,
            "still_running": 0,
            "stopped": 0,
            "no_match": 0,
            "no_page_id": len(no_page_id),
            "errors": 0,
            "snapshot_checked": 0,
            "snapshot_reachable": 0,
            "snapshot_unreachable": 0,
            "snapshot_skipped": 0,
        }

        # ── Stage 1: Meta API check ─────────────────────────────────
        api_checked_ids: set[int] = set()

        if has_api and total_pages > 0:
            print("=" * 60)
            print("STAGE 1: Meta Ad Library API Check")
            print("=" * 60)

            for i, (page_id, page_ads) in enumerate(page_items):
                if time_exceeded():
                    print("  Stage1 aborted by max-seconds limit")
                    break
                ext_id_map = {ad.external_id: ad for ad in page_ads if ad.external_id}
                page_name = (page_ads[0].ad_metadata or {}).get("page_name", "?")
                print(f"[{i+1}/{total_pages}] Page {page_id} ({page_name}) - {len(page_ads)} ads")

                api_results = fetch_ads_by_page_id(page_id, token, request_delay=args.request_delay)
                stats["api_calls"] += 1
                print(f"  API returned {len(api_results)} ads")

                for api_ad in api_results:
                    api_id = api_ad.get("id", "")
                    if api_id in ext_id_map:
                        ad = ext_id_map[api_id]
                        try:
                            survival = check_ad_survival(ad, api_ad)
                            update_ad_survival(ad, survival)
                            api_checked_ids.add(ad.id)
                            stats["api_matched"] += 1

                            if survival["is_running"]:
                                stats["still_running"] += 1
                                status_label = "RUNNING"
                            else:
                                stats["stopped"] += 1
                                status_label = "STOPPED"

                            print(f"    {api_id}: {status_label} ({survival['days_running']}d)")
                        except Exception as e:
                            print(f"    Error updating {api_id}: {e}")
                            stats["errors"] += 1

                # Count unmatched
                matched_ids = {r.get("id") for r in api_results} & set(ext_id_map.keys())
                unmatched = len(ext_id_map) - len(matched_ids)
                if unmatched > 0:
                    stats["no_match"] += unmatched

                session.commit()

                if i + 1 < total_pages:
                    time.sleep(args.request_delay)

        # ── Stage 2: Snapshot URL check ──────────────────────────────
        # Check ads that were NOT verified via API (no_page_id + unmatched)
        print()
        print("=" * 60)
        print("STAGE 2: Snapshot URL HTTP Check")
        print("=" * 60)

        ads_needing_snapshot = [
            ad for ad in ads
            if ad.id not in api_checked_ids and ad.snapshot_url
        ]
        if args.max_snapshot_checks is not None:
            ads_needing_snapshot = ads_needing_snapshot[: max(0, args.max_snapshot_checks)]
        ads_no_snapshot = [
            ad for ad in ads
            if ad.id not in api_checked_ids and not ad.snapshot_url
        ]

        print(f"Ads needing snapshot check: {len(ads_needing_snapshot)}")
        print(f"Ads with no snapshot_url (skipped): {len(ads_no_snapshot)}")
        stats["snapshot_skipped"] = len(ads_no_snapshot)

        for i, ad in enumerate(ads_needing_snapshot):
            if time_exceeded():
                print("  Stage2 aborted by max-seconds limit")
                break
            result = check_snapshot_url(ad.snapshot_url)
            update_ad_snapshot_result(ad, result)
            stats["snapshot_checked"] += 1

            if result["reachable"] is True:
                stats["snapshot_reachable"] += 1
                label = "REACHABLE"
            elif result["reachable"] is False:
                stats["snapshot_unreachable"] += 1
                label = f"UNREACHABLE ({result.get('error') or result.get('status_code', '?')})"
            else:
                label = "UNKNOWN"

            title_safe = (ad.title or "no title")[:40].encode("ascii", "replace").decode("ascii")
            print(f"  [{i+1}/{len(ads_needing_snapshot)}] ID:{ad.id} {label} - {title_safe}")

            # Commit every 50 ads
            if (i + 1) % 50 == 0:
                session.commit()

            # Rate limit snapshot checks
            if i + 1 < len(ads_needing_snapshot):
                time.sleep(args.snapshot_delay)

        # Handle ads without page_id and without snapshot_url
        now = datetime.now(timezone.utc)
        for ad in ads_no_snapshot:
            meta = dict(ad.ad_metadata or {})
            if "last_checked_at" not in meta:
                meta["last_checked_at"] = now.isoformat()
            if "survival_checked_at" not in meta:
                meta["survival_checked_at"] = now.isoformat()
            if "is_still_running" not in meta:
                meta["is_still_running"] = None  # Unknown
            # Estimate days_running from first_seen_at if available
            if ad.first_seen_at and "days_running" not in meta:
                first = ad.first_seen_at
                if first.tzinfo is None:
                    first = first.replace(tzinfo=timezone.utc)
                days = max(1, (now - first).days)
                meta["days_running"] = days
                meta["longevity_class"] = classify_longevity(days)
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

        session.commit()

        # ── Summary ──────────────────────────────────────────────────
        print()
        print("=" * 60)
        print("SURVIVAL CHECK RESULTS")
        print("=" * 60)
        print()
        print("--- Stage 1: Meta API ---")
        print(f"  API calls made:       {stats['api_calls']}")
        print(f"  Ads matched:          {stats['api_matched']}")
        print(f"  Still running (API):  {stats['still_running']}")
        print(f"  Stopped (API):        {stats['stopped']}")
        print(f"  No API match:         {stats['no_match']}")
        print()
        print("--- Stage 2: Snapshot URL ---")
        print(f"  Snapshot checked:     {stats['snapshot_checked']}")
        print(f"  Reachable (alive):    {stats['snapshot_reachable']}")
        print(f"  Unreachable (dead):   {stats['snapshot_unreachable']}")
        print(f"  Skipped (no URL):     {stats['snapshot_skipped']}")
        print()
        print(f"  Errors:               {stats['errors']}")
        print()

        # Final distribution
        print("Longevity distribution:")
        longevity_counts: dict[str, int] = {}
        for ad in session.query(Ad).all():
            lc = (ad.ad_metadata or {}).get("longevity_class", "unclassified")
            longevity_counts[lc] = longevity_counts.get(lc, 0) + 1
        for lc, count in sorted(longevity_counts.items()):
            print(f"  {lc}: {count}")

        # Running status
        print()
        print("Running status (final):")
        running_counts: dict[str, int] = {}
        for ad in session.query(Ad).all():
            status = (ad.ad_metadata or {}).get("is_still_running")
            if status is True:
                label = "running"
            elif status is False:
                label = "stopped"
            else:
                label = "unknown"
            running_counts[label] = running_counts.get(label, 0) + 1
        for label, count in sorted(running_counts.items()):
            print(f"  {label}: {count}")

        print()
        creative_audit = build_creative_library_audit(session, persist=False)["creative_library_audit"]
        print("Creative library audit:")
        print(f"  viewable_rate:        {creative_audit['summary']['creative_viewable_rate']:.2%}")
        print(f"  downloadable_rate:    {creative_audit['summary']['creative_downloadable_rate']:.2%}")
        print(f"  lp_present_rate:      {creative_audit['summary']['lp_present_rate']:.2%}")
        print(f"  lp_resolved_rate:     {creative_audit['summary']['lp_resolved_rate']:.2%}")
        print(f"  missing_media_count:  {creative_audit['summary']['missing_media_count']}")
        print(f"  missing_lp_count:     {creative_audit['summary']['missing_lp_count']}")
        print(f"  lp_unresolved_count:  {creative_audit['summary']['lp_unresolved_count']}")
        print(f"  ops_status:           {creative_audit['slo_status']['overall_status']}")
        print(f"  ops_alerts:           {len(creative_audit['ops_alert_candidates'])}")
        print()
        print("Live ingestion audit:")
        print(f"  daily_new_ads:        {creative_audit['live_ingestion_audit']['daily_new_ads']}")
        print(f"  daily_unique_ads:     {creative_audit['live_ingestion_audit']['daily_unique_ads']}")
        print(f"  duplicate_rate:       {creative_audit['live_ingestion_audit']['duplicate_rate']:.2%}")
        print(f"  stale_ad_rate:        {creative_audit['live_ingestion_audit']['stale_ad_rate']:.2%}")
        print(f"  inactive_keywords_7d: {len(creative_audit['live_ingestion_audit']['inactive_keywords_7d'])}")
        print()
        print("Daily ops report:")
        print(f"  top_regressions:      {len(creative_audit['creative_library_daily_report']['top_regressions'])}")
        print(f"  top_recoveries:       {len(creative_audit['creative_library_daily_report']['top_recoveries'])}")
        print()
        print("Done!")
        if args.max_seconds is not None:
            elapsed = round(time.monotonic() - started, 1)
            print(f"Elapsed: {elapsed}s (limit={args.max_seconds}s)")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
