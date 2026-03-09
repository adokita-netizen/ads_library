#!/usr/bin/env python3
"""Re-crawl existing ads to get updated metrics.

For each ad with an external_id, attempts to fetch current metrics
from the Meta Ad Library API (or falls back to stored data).
Compares new metrics vs stored, computes deltas, and updates metrics_history.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/recrawl_metrics.py
"""

import os
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.orm import sessionmaker

from app.core.database import SyncSessionLocal, is_in_memory_mode
from app.models.ad import Ad

# Maximum history entries per ad
MAX_HISTORY = 30

# API config
GRAPH_API_VERSION = "v25.0"
ADS_ARCHIVE_URL = "https://graph.facebook.com/%s/ads_archive" % GRAPH_API_VERSION
REQUEST_DELAY = 2.0
API_TIMEOUT = 15.0
BATCH_SIZE = 25

# Fields to request
API_FIELDS = ",".join([
    "id",
    "estimated_audience_size",
    "ad_delivery_start_time",
    "ad_delivery_stop_time",
    "publisher_platforms",
])


def _get_access_token() -> str:
    """Load Meta API access token from DB settings."""
    try:
        from app.api.endpoints.settings import load_api_keys_from_db
        keys = load_api_keys_from_db()
        meta_keys = keys.get("meta", keys.get("facebook", {}))
        token = meta_keys.get("access_token")
        if token:
            return token
    except Exception:
        pass
    return ""


def _get_session():
    """Get DB session with SQLite fallback for local ops scripts."""
    if not is_in_memory_mode():
        try:
            session = SyncSessionLocal()
            session.execute(__import__("sqlalchemy").text("SELECT 1"))
            return session
        except Exception:
            pass

    db_path = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")
    if not os.path.exists(db_path):
        raise RuntimeError(f"vaap_local.db not found at {db_path}")
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine)
    return Session()


def _fetch_ads_by_page(page_id: str, token: str) -> list:
    """Fetch ads for a page_id from Meta Ad Library API."""
    if not token:
        return []

    try:
        import httpx
    except ImportError:
        print("  httpx not installed, skipping API fetch")
        return []

    results = []
    params = {
        "access_token": token,
        "search_terms": "",
        "ad_reached_countries": '["JP"]',
        "fields": API_FIELDS,
        "search_page_ids": page_id,
        "limit": BATCH_SIZE,
    }

    try:
        with httpx.Client(timeout=API_TIMEOUT) as client:
            resp = client.get(ADS_ARCHIVE_URL, params=params)
            if resp.status_code == 200:
                data = resp.json()
                results.extend(data.get("data", []))
    except Exception as e:
        print("  API error for page %s: %s" % (page_id, str(e)[:80]))

    return results


def _extract_metrics_from_api(api_data: dict, ad: Ad) -> dict:
    """Extract view/spend/like metrics from API response data."""
    meta = ad.ad_metadata or {}

    # Audience-based view estimation
    audience = api_data.get("estimated_audience_size", {})
    audience_min = audience.get("lower_bound", 0) if isinstance(audience, dict) else 0
    audience_max = audience.get("upper_bound", 0) if isinstance(audience, dict) else 0
    avg_audience = (audience_min + audience_max) / 2 if audience_max > 0 else 0

    views = 0
    if avg_audience > 0:
        # Estimate views from audience * frequency
        frequency = 3.0
        views = int(avg_audience * frequency)
    elif ad.view_count and ad.view_count > 0:
        views = ad.view_count
    elif ad.impressions and ad.impressions > 0:
        views = ad.impressions

    # Spend estimation: (views / 1000) * CPM
    cpm = float(meta.get("estimated_cpm_jpy", 800))
    spend_jpy = (views / 1000.0) * cpm

    # Likes from ad field
    likes = ad.like_count or 0

    return {
        "views": views,
        "spend_jpy": round(spend_jpy, 2),
        "likes": likes,
    }


def _update_history_and_deltas(ad: Ad, new_metrics: dict) -> dict:
    """Add new snapshot to metrics_history and compute deltas.

    Returns the computed deltas dict.
    """
    meta = dict(ad.ad_metadata or {})
    today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    history = list(meta.get("metrics_history", []))

    # Replace if already snapshot today, otherwise prepend
    if history and history[0].get("date") == today_str:
        history[0] = {
            "date": today_str,
            "views": new_metrics["views"],
            "spend_jpy": new_metrics["spend_jpy"],
            "likes": new_metrics["likes"],
        }
    else:
        snapshot = {
            "date": today_str,
            "views": new_metrics["views"],
            "spend_jpy": new_metrics["spend_jpy"],
            "likes": new_metrics["likes"],
        }
        history.insert(0, snapshot)

    # Cap at MAX_HISTORY
    if len(history) > MAX_HISTORY:
        history = history[:MAX_HISTORY]

    meta["metrics_history"] = history

    # Compute deltas
    deltas = {
        "view_increase_daily": 0,
        "spend_increase_daily_jpy": 0.0,
        "like_increase_daily": 0,
        "view_increase_weekly": 0,
        "spend_increase_weekly_jpy": 0.0,
        "snapshot_date": today_str,
    }

    if len(history) >= 2:
        latest = history[0]
        previous = history[1]
        deltas["view_increase_daily"] = max(0, latest["views"] - previous["views"])
        deltas["spend_increase_daily_jpy"] = round(
            max(0.0, latest["spend_jpy"] - previous["spend_jpy"]), 2
        )
        deltas["like_increase_daily"] = max(0, latest["likes"] - previous["likes"])

        # Weekly delta
        if len(history) >= 7:
            week_entry = history[min(6, len(history) - 1)]
        else:
            week_entry = history[-1]
        deltas["view_increase_weekly"] = max(0, latest["views"] - week_entry["views"])
        deltas["spend_increase_weekly_jpy"] = round(
            max(0.0, latest["spend_jpy"] - week_entry["spend_jpy"]), 2
        )

    meta["current_deltas"] = deltas

    ad.ad_metadata = meta
    flag_modified(ad, "ad_metadata")

    return deltas


def main() -> None:
    print("=" * 60)
    print("Re-Crawl Metrics Update")
    print("Executed at: %s" % datetime.now(timezone.utc).isoformat())
    print("=" * 60)

    token = _get_access_token()
    if token:
        print("Meta API token: %s****" % token[:8])
    else:
        print("No Meta API token found. Will use stored data only.")

    session = _get_session()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print("\nTotal ads in database: %d" % total)

        if total == 0:
            print("No ads found. Exiting.")
            return

        # Group ads by page_id for batch API calls
        page_id_map: dict[str, list] = {}
        no_page_ads: list = []

        for ad in ads:
            meta = ad.ad_metadata or {}
            page_id = meta.get("page_id")
            if page_id and token:
                pid = str(page_id)
                if pid not in page_id_map:
                    page_id_map[pid] = []
                page_id_map[pid].append(ad)
            else:
                no_page_ads.append(ad)

        total_updated = 0
        total_api_fetched = 0
        sum_view_increase = 0
        sum_spend_increase = 0.0

        # Process ads with page_id via API
        if page_id_map and token:
            print("\nFetching updated metrics from Meta API for %d pages..." % len(page_id_map))
            for i, (page_id, page_ads) in enumerate(page_id_map.items()):
                ext_id_lookup = {ad.external_id: ad for ad in page_ads if ad.external_id}

                api_results = _fetch_ads_by_page(page_id, token)
                if api_results:
                    print("  [%d/%d] Page %s: %d API results" % (
                        i + 1, len(page_id_map), page_id, len(api_results)))

                for api_ad in api_results:
                    api_id = api_ad.get("id", "")
                    if api_id in ext_id_lookup:
                        ad = ext_id_lookup[api_id]
                        new_metrics = _extract_metrics_from_api(api_ad, ad)
                        deltas = _update_history_and_deltas(ad, new_metrics)
                        total_api_fetched += 1
                        total_updated += 1
                        sum_view_increase += deltas["view_increase_daily"]
                        sum_spend_increase += deltas["spend_increase_daily_jpy"]

                if i + 1 < len(page_id_map):
                    time.sleep(REQUEST_DELAY)

            session.commit()
            print("  API fetch complete: %d ads updated from API." % total_api_fetched)

        # Process remaining ads using stored data
        remaining = [ad for ad in ads
                     if ad not in [a for page_ads in page_id_map.values() for a in page_ads
                                   if a.external_id and (a.ad_metadata or {}).get("page_id")]]
        # Simpler: just process all ads that weren't updated via API
        updated_ids = set()
        if page_id_map:
            for page_ads in page_id_map.values():
                for ad in page_ads:
                    if ad.id in updated_ids:
                        continue
                    # Already processed via API above

        print("\nUpdating %d ads using stored data..." % len(no_page_ads))
        for ad in no_page_ads:
            meta = ad.ad_metadata or {}
            est = meta.get("estimated_metrics", {})

            # Use current best available metrics
            views = 0
            if ad.view_count and ad.view_count > 0:
                views = ad.view_count
            elif ad.impressions and ad.impressions > 0:
                views = ad.impressions
            elif est.get("total_views", 0) > 0:
                views = est["total_views"]

            spend_jpy = 0.0
            if ad.spend and ad.spend > 0:
                spend_jpy = float(ad.spend)
            elif est.get("estimated_total_spend_jpy", 0) > 0:
                spend_jpy = float(est["estimated_total_spend_jpy"])

            likes = ad.like_count or 0

            new_metrics = {
                "views": views,
                "spend_jpy": round(spend_jpy, 2),
                "likes": likes,
            }

            deltas = _update_history_and_deltas(ad, new_metrics)
            total_updated += 1
            sum_view_increase += deltas["view_increase_daily"]
            sum_spend_increase += deltas["spend_increase_daily_jpy"]

        session.commit()

        # Summary
        avg_view_inc = sum_view_increase / total_updated if total_updated > 0 else 0
        avg_spend_inc = sum_spend_increase / total_updated if total_updated > 0 else 0

        print("\n--- Re-Crawl Results ---")
        print("  Total ads updated: %d" % total_updated)
        print("  Updated from API: %d" % total_api_fetched)
        print("  Updated from stored data: %d" % (total_updated - total_api_fetched))
        print("  Avg daily view increase: %.0f" % avg_view_inc)
        print("  Avg daily spend increase: %.2f JPY" % avg_spend_inc)
        print("\nDone!")

    except Exception as e:
        session.rollback()
        print("ERROR: %s" % e)
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
