"""A39: audit freshness + LP metadata coverage.

Usage:
    python -m scripts.audit_data_freshness
    python -m scripts.audit_data_freshness --json-report exports/data_freshness_audit.json
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


def _parse_dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _platform_name(ad: Ad) -> str:
    platform = getattr(ad, "platform", None)
    if platform is None:
        return "unknown"
    return str(getattr(platform, "value", platform)).lower()


def _crawl_timestamp(ad: Ad) -> datetime | None:
    meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
    return (
        _parse_dt(meta.get("last_crawled_at"))
        or _parse_dt(meta.get("freshness_updated_at"))
        or _parse_dt(getattr(ad, "updated_at", None))
        or _parse_dt(getattr(ad, "last_seen_at", None))
    )


def _lp_info_present(meta: dict) -> bool:
    lp_info = meta.get("lp_info") if isinstance(meta.get("lp_info"), dict) else {}
    return bool(
        lp_info.get("final_url")
        or lp_info.get("title")
        or lp_info.get("description")
        or lp_info.get("canonical")
        or lp_info.get("og_image")
    )


def _build_platform_row(label: str) -> dict:
    return {
        "platform": label,
        "total_ads": 0,
        "updated_24h_count": 0,
        "lp_info_present_count": 0,
        "stale_count": 0,
    }


def build_data_freshness_audit(
    session,
    *,
    now: datetime | None = None,
    stale_after_hours: int = 24,
    top_n: int = 20,
) -> dict:
    now = now or datetime.now(timezone.utc)
    stale_cutoff = now - timedelta(hours=max(1, stale_after_hours))
    rows = []
    platform_rows: dict[str, dict] = defaultdict(lambda: _build_platform_row("unknown"))

    ads = session.query(Ad).order_by(Ad.updated_at.desc()).all()
    total_ads = len(ads)
    updated_24h_count = 0
    lp_info_present_count = 0

    for ad in ads:
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
        crawled_at = _crawl_timestamp(ad)
        platform = _platform_name(ad)
        bucket = platform_rows[platform]
        bucket["platform"] = platform
        bucket["total_ads"] += 1

        is_updated_24h = bool(crawled_at and crawled_at >= stale_cutoff)
        has_lp_info = _lp_info_present(meta)
        freshness_score = meta.get("freshness_score")

        if is_updated_24h:
            updated_24h_count += 1
            bucket["updated_24h_count"] += 1
        else:
            bucket["stale_count"] += 1

        if has_lp_info:
            lp_info_present_count += 1
            bucket["lp_info_present_count"] += 1

        if not is_updated_24h:
            rows.append(
                {
                    "ad_id": ad.id,
                    "title": ad.title or "",
                    "platform": platform,
                    "advertiser_name": ad.advertiser_name or "",
                    "last_crawled_at": crawled_at.isoformat() if crawled_at else None,
                    "freshness_score": freshness_score,
                    "lp_fetch_error_code": meta.get("lp_fetch_error_code"),
                }
            )

    platform_breakdown = []
    for bucket in platform_rows.values():
        total = bucket["total_ads"] or 1
        bucket["updated_24h_rate"] = round(bucket["updated_24h_count"] / total, 4)
        bucket["lp_info_present_rate"] = round(bucket["lp_info_present_count"] / total, 4)
        platform_breakdown.append(bucket)
    platform_breakdown.sort(key=lambda item: (item["updated_24h_rate"], item["platform"]))

    rows.sort(key=lambda item: (item["last_crawled_at"] is not None, item["last_crawled_at"] or ""))

    report = {
        "generated_at": now.isoformat(),
        "summary": {
            "total_ads": total_ads,
            "updated_24h_count": updated_24h_count,
            "updated_24h_rate": round(updated_24h_count / total_ads, 4) if total_ads else 0.0,
            "lp_info_present_count": lp_info_present_count,
            "lp_info_missing_count": max(0, total_ads - lp_info_present_count),
            "lp_info_missing_rate": round((total_ads - lp_info_present_count) / total_ads, 4) if total_ads else 0.0,
        },
        "platform_breakdown": platform_breakdown,
        "stale_ads_top_n": rows[: max(1, top_n)],
        "warnings": [],
    }
    if report["summary"]["updated_24h_rate"] < 0.8:
        report["warnings"].append("freshness_24h_rate_below_threshold")
    if report["summary"]["lp_info_missing_rate"] > 0.3:
        report["warnings"].append("lp_info_missing_rate_above_threshold")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit ad freshness and LP info completeness")
    parser.add_argument("--stale-after-hours", type=int, default=24)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--json-report", type=str)
    args = parser.parse_args()

    session = SyncSessionLocal()
    try:
        report = build_data_freshness_audit(
            session,
            stale_after_hours=args.stale_after_hours,
            top_n=args.top_n,
        )
    finally:
        session.close()

    summary = report["summary"]
    print(f"total_ads:             {summary['total_ads']}")
    print(f"updated_24h_rate:      {summary['updated_24h_rate']:.2%}")
    print(f"lp_info_missing_rate:  {summary['lp_info_missing_rate']:.2%}")
    print(f"warnings:              {', '.join(report['warnings']) or 'none'}")

    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(f"report:                {args.json_report}")


if __name__ == "__main__":
    main()
