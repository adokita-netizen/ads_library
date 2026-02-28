"""Meta Ad Library API から広告の実配信データを収集する。

商用広告でも取得可能なフィールド:
  - estimated_audience_size (推定オーディエンスサイズ)
  - publisher_platforms (配信プラットフォーム)
  - ad_delivery_start_time / stop_time (配信期間)

これらを使ってより正確なメトリクス推定を行う。

Run from the backend directory:
    cd backend
    python scripts/collect_real_metrics.py
"""

import sys
import time

sys.path.insert(0, ".")

import httpx
from datetime import datetime, timezone
from sqlalchemy import func
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.api.endpoints.settings import load_api_keys_from_db


# ── Config ────────────────────────────────────────────────────────

GRAPH_API_VERSION = "v25.0"
ADS_ARCHIVE_URL = f"https://graph.facebook.com/{GRAPH_API_VERSION}/ads_archive"
REQUEST_DELAY = 2.0  # seconds between API calls (200 calls/hour limit)
API_TIMEOUT = 15.0
PAGE_LIMIT = 25  # results per API call

# Fields to request from ads_archive
API_FIELDS = ",".join([
    "id",
    "ad_delivery_start_time",
    "ad_delivery_stop_time",
    "estimated_audience_size",
    "publisher_platforms",
    "page_name",
    "ad_snapshot_url",
    "ad_creative_bodies",
    "ad_creative_link_captions",
    "ad_creative_link_titles",
])

# Genre multipliers for CPM estimation
GENRE_CPM_MULTIPLIERS = {
    "beauty": 1.3, "health": 1.2, "ec_d2c": 1.1,
    "finance": 1.5, "app": 0.9, "food": 1.0,
    "education": 1.1, "technology": 1.2, "other": 1.0,
}


# ── API Functions ─────────────────────────────────────────────────


def get_access_token() -> str:
    keys = load_api_keys_from_db()
    meta_keys = keys.get("meta", keys.get("facebook", {}))
    token = meta_keys.get("access_token")
    if not token:
        raise ValueError("Meta access_token が設定されていません。Settings画面で設定してください。")
    return token


def fetch_ads_by_page_id(page_id: str, token: str) -> list[dict]:
    """Fetch all ads for a page_id from Meta Ad Library API."""
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
            # First page
            resp = client.get(ADS_ARCHIVE_URL, params=params)
            if resp.status_code != 200:
                error = resp.json().get("error", {}).get("message", resp.text[:100])
                print(f"    API error for page {page_id}: {error}")
                return []

            data = resp.json()
            all_results.extend(data.get("data", []))

            # Pagination (follow "next" link)
            pages_fetched = 1
            while "paging" in data and "next" in data["paging"] and pages_fetched < 10:
                time.sleep(REQUEST_DELAY)
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


# ── Data Update Functions ─────────────────────────────────────────


def update_ad_with_api_data(ad: Ad, api_data: dict) -> bool:
    """Update an Ad record with data from the Meta Ad Library API."""
    updated = False
    meta = dict(ad.ad_metadata or {})

    # 配信期間の更新
    start_time = api_data.get("ad_delivery_start_time")
    stop_time = api_data.get("ad_delivery_stop_time")

    if start_time:
        meta["delivery_start_time"] = start_time
        if not ad.first_seen_at:
            try:
                ad.first_seen_at = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass
        updated = True

    if stop_time:
        meta["delivery_stop_time"] = stop_time
        meta["is_still_running"] = False
    else:
        meta["is_still_running"] = True

    # オーディエンスサイズ
    audience = api_data.get("estimated_audience_size")
    if audience and isinstance(audience, dict):
        meta["estimated_audience_min"] = audience.get("lower_bound")
        meta["estimated_audience_max"] = audience.get("upper_bound")
        updated = True

    # 配信プラットフォーム
    platforms = api_data.get("publisher_platforms")
    if platforms and isinstance(platforms, list):
        meta["publisher_platforms"] = platforms
        updated = True

    # メトリクスの再計算（実データベース）
    if audience and start_time:
        _recalculate_metrics(ad, meta)
        updated = True

    if updated:
        meta["metrics_collection_time"] = datetime.now(timezone.utc).isoformat()
        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")

    return updated


def _recalculate_metrics(ad: Ad, meta: dict):
    """Recalculate metrics using audience-based estimation (more accurate than CPM)."""
    audience_min = meta.get("estimated_audience_min") or 0
    audience_max = meta.get("estimated_audience_max") or 0
    avg_audience = (audience_min + audience_max) / 2 if audience_max > 0 else 0

    if avg_audience == 0:
        return

    # 配信日数
    start_str = meta.get("delivery_start_time")
    stop_str = meta.get("delivery_stop_time")
    if start_str:
        try:
            start = datetime.fromisoformat(start_str.replace("Z", "+00:00"))
            end = datetime.fromisoformat(stop_str.replace("Z", "+00:00")) if stop_str else datetime.now(timezone.utc)
            days_running = max(1, (end - start).days)
        except (ValueError, TypeError):
            days_running = 1
    else:
        days_running = 1

    # プラットフォーム数による補正
    platforms = meta.get("publisher_platforms", [])
    platform_multiplier = max(1.0, len(platforms) * 0.8)

    # フリークエンシー推定 (配信日数が長いほど高い)
    estimated_frequency = 3.0
    if days_running > 90:
        estimated_frequency = 4.5
    elif days_running > 30:
        estimated_frequency = 3.5

    # インプレッション推定
    impressions = int(avg_audience * estimated_frequency * platform_multiplier)
    meta["impressions_from_audience"] = impressions
    meta["estimation_method"] = "audience_based"
    meta["estimation_confidence"] = 0.65

    ad.impressions = impressions
    ad.view_count = impressions

    # Spend推定
    base_cpm = 800  # JPY
    category_val = ad.category.value if ad.category and hasattr(ad.category, "value") else "other"
    cpm = base_cpm * GENRE_CPM_MULTIPLIERS.get(category_val, 1.0)
    ad.spend = round(impressions * cpm / 1000)
    meta["estimated_spend_jpy"] = ad.spend
    meta["estimated_cpm_jpy"] = cpm
    meta["estimated_days_running"] = days_running


# ── Main ──────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        token = get_access_token()
        print(f"Meta access token: {token[:8]}****")
        print()

        # Group ads by page_id
        ads = session.query(Ad).all()
        page_id_to_ads: dict[str, list[Ad]] = {}
        no_page_id = []

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

        total_ads = len(ads)
        total_pages = len(page_id_to_ads)
        print(f"Total ads: {total_ads}")
        print(f"Unique page_ids: {total_pages}")
        print(f"Ads without page_id: {len(no_page_id)}")
        print()

        # Fetch data from API for each page
        stats = {"updated": 0, "matched": 0, "api_calls": 0, "no_match": 0, "errors": 0}

        for i, (page_id, page_ads) in enumerate(page_id_to_ads.items()):
            ext_id_map = {ad.external_id: ad for ad in page_ads if ad.external_id}
            print(f"[{i+1}/{total_pages}] Page {page_id} ({len(page_ads)} ads)")

            api_results = fetch_ads_by_page_id(page_id, token)
            stats["api_calls"] += 1
            print(f"  API returned {len(api_results)} ads")

            for api_ad in api_results:
                api_id = api_ad.get("id", "")
                if api_id in ext_id_map:
                    ad = ext_id_map[api_id]
                    try:
                        if update_ad_with_api_data(ad, api_ad):
                            stats["updated"] += 1
                        stats["matched"] += 1
                    except Exception as e:
                        print(f"    Error updating Ad {ad.id}: {e}")
                        stats["errors"] += 1

            # How many of our ads were matched?
            matched_ids = {r.get("id") for r in api_results} & set(ext_id_map.keys())
            unmatched = len(ext_id_map) - len(matched_ids)
            if unmatched > 0:
                stats["no_match"] += unmatched
                print(f"  {unmatched} ads not found in API response")

            # Commit per page batch
            session.commit()

            # Rate limit
            if i + 1 < total_pages:
                time.sleep(REQUEST_DELAY)

        # Handle ads without page_id: try searching by external_id directly
        if no_page_id:
            print(f"\nProcessing {len(no_page_id)} ads without page_id...")
            for ad in no_page_id:
                if not ad.external_id:
                    continue
                # Search by external_id in search_terms (may not always work)
                try:
                    params = {
                        "access_token": token,
                        "search_terms": "",
                        "ad_reached_countries": '["JP"]',
                        "fields": API_FIELDS,
                        "limit": 5,
                    }
                    with httpx.Client(timeout=API_TIMEOUT) as client:
                        resp = client.get(
                            f"https://graph.facebook.com/{GRAPH_API_VERSION}/{ad.external_id}",
                            params={"fields": "ad_snapshot_url", "access_token": token},
                        )
                        # This usually returns 400 for ad library ads, just mark as no_match
                except Exception:
                    pass
                stats["no_match"] += 1

        session.commit()

        # Summary
        print()
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"API calls made:     {stats['api_calls']}")
        print(f"Ads matched:        {stats['matched']}")
        print(f"Ads updated:        {stats['updated']}")
        print(f"No API match:       {stats['no_match']}")
        print(f"Errors:             {stats['errors']}")
        print()

        # Verify improvements
        has_audience = session.query(Ad).filter(
            Ad.ad_metadata.like('%"estimated_audience_min"%')
        ).count()
        has_running = session.query(Ad).filter(
            Ad.ad_metadata.like('%"is_still_running"%')
        ).count()
        has_platforms = session.query(Ad).filter(
            Ad.ad_metadata.like('%"publisher_platforms"%')
        ).count()

        print(f"Ads with audience data:   {has_audience}")
        print(f"Ads with running status:  {has_running}")
        print(f"Ads with platform data:   {has_platforms}")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
