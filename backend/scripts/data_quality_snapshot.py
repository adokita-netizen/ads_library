"""A-R3-1: Persist a daily data quality snapshot."""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import func, select, text

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.data_quality import DataQualitySnapshot
from app.services.data_quality_report import (
    build_bedrock_precision_roi_audit,
    build_japanese_inventory_audit,
    build_meta_completion_audit,
    build_numeric_truth_audit,
)


def _calc_field_fill_rates(session) -> tuple[int, dict[str, float]]:
    total_ads = int(session.query(func.count(Ad.id)).scalar() or 0)
    if total_ads <= 0:
        return 0, {}

    fields = {
        "title": Ad.title,
        "category": Ad.category,
        "destination_url": Ad.destination_url,
        "platform": Ad.platform,
        "advertiser_name": Ad.advertiser_name,
        "creative_type": Ad.creative_type,
        "thumbnail_url": Ad.thumbnail_url,
        "video_url": Ad.video_url,
    }
    rates: dict[str, float] = {}
    for name, col in fields.items():
        count = int(session.query(func.count(Ad.id)).filter(col.isnot(None)).scalar() or 0)
        rates[name] = round((count / total_ads) * 100.0, 1)
    return total_ads, rates


def _calc_freshness_score(session) -> float:
    row = session.execute(
        text(
            """
            SELECT AVG((ad_metadata->>'freshness_score')::float)
            FROM ads
            WHERE ad_metadata->>'freshness_score' IS NOT NULL
            """
        )
    ).fetchone()
    return round(float(row[0]), 1) if row and row[0] is not None else 0.0


def run_snapshot(snapshot_date: date | None = None) -> dict:
    target_date = snapshot_date or date.today()
    session = SyncSessionLocal()
    try:
        total_ads, field_fill_rates = _calc_field_fill_rates(session)
        fill_rate = round(sum(field_fill_rates.values()) / len(field_fill_rates), 1) if field_fill_rates else 0.0
        null_rate = round(100.0 - fill_rate, 1)
        freshness_score = _calc_freshness_score(session)
        numeric_truth = build_numeric_truth_audit(session, target_date=target_date, top_n=10)
        japanese_inventory = build_japanese_inventory_audit(session, target_date=target_date, top_n=10)
        bedrock_precision = build_bedrock_precision_roi_audit(session, target_date=target_date, top_n=10)
        meta_completion = build_meta_completion_audit(session, target_date=target_date, top_n=10)
        field_fill_rates = {
            **field_fill_rates,
            "numeric_truth": {
                "estimated_only_count": numeric_truth["summary"]["estimated_only_count"],
                "missing_numeric_count": numeric_truth["summary"]["missing_numeric_count"],
                "stale_real_metrics_count": numeric_truth["summary"]["stale_real_metrics_count"],
            },
            "japanese_inventory": {
                "jp_rate": japanese_inventory["summary"]["jp_rate"],
                "non_jp_rate": japanese_inventory["summary"]["non_jp_rate"],
                "unknown_rate": japanese_inventory["summary"]["unknown_rate"],
                "manual_review_count": japanese_inventory["summary"]["manual_review_count"],
            },
            "bedrock_precision_roi": {
                "rule_only_count": bedrock_precision["summary"]["rule_only_count"],
                "bedrock_used_count": bedrock_precision["summary"]["bedrock_used_count"],
                "manual_review_count": bedrock_precision["summary"]["manual_review_count"],
                "bedrock_valuable_count": bedrock_precision["summary"]["bedrock_valuable_count"],
            },
            "meta_completion_acceptance": {
                "total_meta_ads": meta_completion["summary"]["total_meta_ads"],
                "real_metrics_rate": meta_completion["summary"]["real_metrics_rate"],
                "jp_rate": meta_completion["summary"]["jp_rate"],
                "new_saved_rate": meta_completion["summary"]["new_saved_rate"],
                "lp_attached_rate": meta_completion["summary"]["lp_attached_rate"],
                "creative_attached_rate": meta_completion["summary"]["creative_attached_rate"],
                "completion_score": meta_completion["summary"]["completion_score"],
                "accepted_80": meta_completion["summary"]["accepted_80"],
                "accepted_90": meta_completion["summary"]["accepted_90"],
            },
        }

        existing = (
            session.execute(
                select(DataQualitySnapshot).where(DataQualitySnapshot.snapshot_date == target_date)
            )
            .scalars()
            .first()
        )
        if existing:
            existing.total_ads = total_ads
            existing.null_rate = null_rate
            existing.fill_rate = fill_rate
            existing.freshness_score = freshness_score
            existing.field_fill_rates = field_fill_rates
            existing.updated_at = datetime.now(timezone.utc)
            mode = "updated"
        else:
            session.add(
                DataQualitySnapshot(
                    snapshot_date=target_date,
                    total_ads=total_ads,
                    null_rate=null_rate,
                    fill_rate=fill_rate,
                    freshness_score=freshness_score,
                    field_fill_rates=field_fill_rates,
                )
            )
            mode = "created"

        session.commit()
        return {
            "status": "ok",
            "mode": mode,
            "snapshot_date": target_date.isoformat(),
            "total_ads": total_ads,
            "null_rate": null_rate,
            "fill_rate": fill_rate,
            "freshness_score": freshness_score,
        }
    finally:
        session.close()


if __name__ == "__main__":
    result = run_snapshot()
    print(result)
