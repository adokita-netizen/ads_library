"""A-R2-1: Production data quality fix.

Surveys and fixes NULL/missing fields across all ads:
  Step 1: Survey current data quality
  Step 2: Fix category NULL using classify_ads logic
  Step 3: Fix title NULL/empty
  Step 4: Supplement ad_metadata missing keys (days_running, is_still_running, longevity_class)
  Step 5: Report final state

Usage:
    python -m scripts.r2_data_quality_fix               # survey only
    python -m scripts.r2_data_quality_fix --fix          # survey + fix
    python -m scripts.r2_data_quality_fix --json-report exports/r2_quality.json
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import func, text
from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# Metadata keys that should be present on every ad
REQUIRED_META_KEYS = [
    "latest_hit_score",
    "creative_quality",
    "is_still_running",
    "days_running",
    "longevity_class",
]

RECOMMENDED_META_KEYS = [
    "publisher_platforms",
    "estimation_method",
    "delivery_start_time",
    "freshness_score",
    "ranking_metrics",
    "creative_analysis",
    "keywords",
]


def survey(session) -> dict:
    """Survey data quality and return a report."""
    total = session.query(func.count(Ad.id)).scalar()
    report = {"total_ads": total, "fields": {}, "metadata": {}}

    if total == 0:
        return report

    # Column NULL checks
    field_checks = {
        "title": Ad.title,
        "category": Ad.category,
        "platform": Ad.platform,
        "advertiser_name": Ad.advertiser_name,
        "creative_type": Ad.creative_type,
        "destination_url": Ad.destination_url,
        "thumbnail_url": Ad.thumbnail_url,
        "image_url": Ad.image_url,
        "video_url": Ad.video_url,
    }

    for name, col in field_checks.items():
        null_count = session.query(func.count(Ad.id)).filter(col == None).scalar()
        fill_pct = round((total - null_count) / total * 100, 1)
        report["fields"][name] = {
            "null_count": null_count,
            "fill_pct": fill_pct,
        }

    # Title empty string check
    empty_title = session.query(func.count(Ad.id)).filter(Ad.title == "").scalar()
    report["fields"]["title"]["empty_count"] = empty_title

    # Metadata key checks (DB-agnostic: works on both PostgreSQL and SQLite)
    ads_meta = session.query(Ad.ad_metadata).all()
    for key in REQUIRED_META_KEYS + RECOMMENDED_META_KEYS:
        is_required = key in REQUIRED_META_KEYS
        count = 0
        for (meta,) in ads_meta:
            meta_dict = meta if isinstance(meta, dict) else {}
            if meta_dict.get(key) is None:
                count += 1
        fill_pct = round((total - count) / total * 100, 1)
        report["metadata"][key] = {
            "missing": count,
            "fill_pct": fill_pct,
            "required": is_required,
        }

    return report


def fix_categories(session) -> int:
    """Fix NULL category ads using keyword-based classification."""
    ads = session.query(Ad).filter(Ad.category == None).all()
    if not ads:
        return 0

    from app.models.ad import AdCategoryEnum

    # Simple keyword-based classification
    category_keywords = {
        AdCategoryEnum.BEAUTY: ["コスメ", "美容", "スキンケア", "化粧", "メイク", "シャンプー", "ヘアケア"],
        AdCategoryEnum.HEALTH: ["サプリ", "健康", "ダイエット", "プロテイン", "乳酸菌", "ビタミン"],
        AdCategoryEnum.FOOD: ["食品", "グルメ", "おいしい", "レシピ"],
        AdCategoryEnum.FINANCE: ["投資", "ローン", "カード", "保険", "FX", "証券"],
        AdCategoryEnum.EDUCATION: ["学習", "資格", "英語", "プログラミング", "スクール"],
        AdCategoryEnum.GAMING: ["ゲーム", "RPG", "アプリゲーム"],
        AdCategoryEnum.EC_D2C: ["通販", "ショッピング", "EC", "D2C", "セール"],
        AdCategoryEnum.APP: ["アプリ", "ダウンロード"],
        AdCategoryEnum.TECHNOLOGY: ["テクノロジー", "AI", "クラウド", "SaaS"],
    }

    fixed = 0
    for ad in ads:
        text_content = " ".join(filter(None, [ad.title, ad.description, ad.advertiser_name]))
        if not text_content:
            ad.category = AdCategoryEnum.OTHER
            fixed += 1
            continue

        matched = None
        for cat, keywords in category_keywords.items():
            for kw in keywords:
                if kw in text_content:
                    matched = cat
                    break
            if matched:
                break

        ad.category = matched or AdCategoryEnum.OTHER
        fixed += 1

    if fixed > 0:
        session.flush()
    return fixed


def fix_metadata_gaps(session) -> dict:
    """Fill missing ad_metadata keys with reasonable defaults."""
    ads = session.query(Ad).all()
    fixes = {"days_running": 0, "is_still_running": 0, "longevity_class": 0}

    for ad in ads:
        meta = dict(ad.ad_metadata or {})
        changed = False

        # days_running
        if "days_running" not in meta or meta["days_running"] is None:
            if ad.first_seen_at and ad.last_seen_at:
                first = ad.first_seen_at if ad.first_seen_at.tzinfo else ad.first_seen_at.replace(tzinfo=timezone.utc)
                last = ad.last_seen_at if ad.last_seen_at.tzinfo else ad.last_seen_at.replace(tzinfo=timezone.utc)
                meta["days_running"] = max(1, (last - first).days)
            else:
                meta["days_running"] = 1
            fixes["days_running"] += 1
            changed = True

        # is_still_running
        if "is_still_running" not in meta:
            meta["is_still_running"] = False  # conservative default
            fixes["is_still_running"] += 1
            changed = True

        # longevity_class
        if "longevity_class" not in meta:
            days = meta.get("days_running", 1)
            if days <= 7:
                meta["longevity_class"] = "flash"
            elif days <= 30:
                meta["longevity_class"] = "short_runner"
            elif days <= 90:
                meta["longevity_class"] = "medium_runner"
            else:
                meta["longevity_class"] = "long_runner"
            fixes["longevity_class"] += 1
            changed = True

        # creative_quality (basic)
        if "creative_quality" not in meta:
            quality = {"has_thumbnail": bool(ad.thumbnail_url), "has_image": bool(ad.image_url)}
            if ad.video_url:
                quality["has_video"] = True
            meta["creative_quality"] = quality
            changed = True

        if changed:
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

    session.flush()
    return fixes


def main():
    parser = argparse.ArgumentParser(description="R2 data quality fix")
    parser.add_argument("--fix", action="store_true", help="Apply fixes (default: survey only)")
    parser.add_argument("--json-report", type=str, help="Export report to JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("  A-R2-1: Production Data Quality Fix")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        # Step 1: Survey
        print("\n  Step 1: Survey...")
        report = survey(session)

        print(f"\n  Total ads: {report['total_ads']}")
        print("\n  Field fill rates:")
        for name, info in report["fields"].items():
            icon = "OK" if info["fill_pct"] >= 95 else "!!"
            extra = f" ({info.get('empty_count', 0)} empty)" if info.get("empty_count") else ""
            print(f"    [{icon}] {name:25s} {info['fill_pct']:5.1f}%  ({info['null_count']} NULL){extra}")

        print("\n  Metadata key fill rates:")
        for key, info in report["metadata"].items():
            req = "*" if info["required"] else " "
            icon = "OK" if info["fill_pct"] >= 95 else ("!!" if info["required"] else "--")
            print(f"    [{icon}]{req} {key:25s} {info['fill_pct']:5.1f}%  ({info['missing']} missing)")

        if not args.fix:
            print("\n  SURVEY ONLY. Use --fix to apply corrections.")
        else:
            # Step 2: Fix categories
            print("\n  Step 2: Fixing categories...")
            cat_fixed = fix_categories(session)
            print(f"    Fixed: {cat_fixed}")

            # Step 3: Fix metadata gaps
            print("\n  Step 3: Fixing metadata gaps...")
            meta_fixes = fix_metadata_gaps(session)
            for k, v in meta_fixes.items():
                print(f"    {k}: {v} fixed")

            session.commit()

            # Re-survey
            print("\n  Post-fix survey:")
            post_report = survey(session)
            for name, info in post_report["fields"].items():
                if info["fill_pct"] < 100:
                    print(f"    {name}: {info['fill_pct']}%")

            report["post_fix"] = post_report
            report["fixes"] = {"categories": cat_fixed, "metadata": meta_fixes}

        if args.json_report:
            os.makedirs(os.path.dirname(args.json_report) or ".", exist_ok=True)
            with open(args.json_report, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2, default=str)
            print(f"\n  Exported: {args.json_report}")

        print()

    except Exception as e:
        session.rollback()
        print(f"\n  ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
