"""Audit creative and LP completeness for ads.

Usage:
    python -m scripts.audit_creative_lp_completeness
    python -m scripts.audit_creative_lp_completeness --json-report exports/creative_lp_audit.json
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


def _meta(ad: Ad) -> dict:
    return ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}


def _lp_info(meta: dict) -> dict:
    return meta.get("lp_info") if isinstance(meta.get("lp_info"), dict) else {}


def _lp_data(meta: dict) -> dict:
    return meta.get("lp_data") if isinstance(meta.get("lp_data"), dict) else {}


def _has_lp_content(meta: dict) -> bool:
    info = _lp_info(meta)
    data = _lp_data(meta)
    return bool(
        info.get("title")
        or info.get("description")
        or info.get("og_image")
        or data.get("full_text_content")
        or data.get("hero_headline")
    )


def build_report(session) -> dict:
    ads = session.query(Ad).order_by(Ad.id.asc()).all()
    total = len(ads)
    media_statuses = Counter()
    creative_reasons = Counter()
    lp_reasons = Counter()
    samples: list[dict] = []

    counts = Counter()
    for ad in ads:
        meta = _meta(ad)
        info = _lp_info(meta)
        data = _lp_data(meta)

        has_thumbnail = bool(ad.thumbnail_url or ad.thumbnail_s3_key)
        has_image = bool(ad.image_url or ad.image_s3_key)
        has_video = bool(ad.video_url or ad.video_s3_key or ad.s3_key)
        has_any_creative = bool(has_thumbnail or has_image or has_video or ad.snapshot_url)
        downloadable_creative = bool(ad.thumbnail_s3_key or ad.image_s3_key or ad.video_s3_key or ad.s3_key)
        has_destination = bool(ad.destination_url or info.get("final_url") or data.get("final_url"))
        has_lp_metadata = bool(info.get("final_url") or info.get("title") or info.get("description") or info.get("og_image"))
        has_lp_content = _has_lp_content(meta)

        counts["has_thumbnail"] += int(has_thumbnail)
        counts["has_image"] += int(has_image)
        counts["has_video"] += int(has_video)
        counts["has_any_creative"] += int(has_any_creative)
        counts["downloadable_creative"] += int(downloadable_creative)
        counts["has_destination"] += int(has_destination)
        counts["has_lp_metadata"] += int(has_lp_metadata)
        counts["has_lp_content"] += int(has_lp_content)

        media_statuses[str(ad.media_extraction_status or "null")] += 1
        creative_reasons[str(meta.get("creative_fetch_reason") or "null")] += 1
        lp_reasons[str(meta.get("lp_fetch_error_code") or meta.get("lp_status") or "null")] += 1

        if len(samples) < 25 and (not downloadable_creative or not has_lp_content):
            samples.append(
                {
                    "ad_id": ad.id,
                    "advertiser_name": ad.advertiser_name,
                    "creative_type": ad.creative_type,
                    "media_extraction_status": ad.media_extraction_status,
                    "destination_url": ad.destination_url,
                    "lp_final_url": info.get("final_url") or data.get("final_url"),
                    "creative_fetch_reason": meta.get("creative_fetch_reason"),
                    "lp_fetch_error_code": meta.get("lp_fetch_error_code"),
                    "has_thumbnail": has_thumbnail,
                    "has_image": has_image,
                    "has_video": has_video,
                    "downloadable_creative": downloadable_creative,
                    "has_lp_content": has_lp_content,
                }
            )

    def pct(value: int) -> float:
        return round(value / total, 4) if total else 0.0

    summary = {
        "total_ads": total,
        "thumbnail_rate": pct(counts["has_thumbnail"]),
        "image_rate": pct(counts["has_image"]),
        "video_rate": pct(counts["has_video"]),
        "creative_any_rate": pct(counts["has_any_creative"]),
        "downloadable_creative_rate": pct(counts["downloadable_creative"]),
        "destination_rate": pct(counts["has_destination"]),
        "lp_metadata_rate": pct(counts["has_lp_metadata"]),
        "lp_content_rate": pct(counts["has_lp_content"]),
        "full_completion_rate": pct(
            sum(
                1
                for ad in ads
                if (
                    bool(ad.thumbnail_url or ad.thumbnail_s3_key or ad.image_url or ad.image_s3_key or ad.video_url or ad.video_s3_key or ad.s3_key)
                    and bool(ad.thumbnail_s3_key or ad.image_s3_key or ad.video_s3_key or ad.s3_key)
                    and bool(ad.destination_url or _lp_info(_meta(ad)).get("final_url") or _lp_data(_meta(ad)).get("final_url"))
                    and _has_lp_content(_meta(ad))
                )
            )
        ),
    }

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": summary,
        "media_status_breakdown": dict(media_statuses.most_common()),
        "creative_reason_breakdown": dict(creative_reasons.most_common(10)),
        "lp_reason_breakdown": dict(lp_reasons.most_common(10)),
        "sample_incomplete_ads": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit creative/LP completeness")
    parser.add_argument("--json-report", type=str)
    args = parser.parse_args()

    session = SyncSessionLocal()
    try:
        report = build_report(session)
    finally:
        session.close()

    summary = report["summary"]
    print(f"total_ads:                  {summary['total_ads']}")
    print(f"creative_any_rate:          {summary['creative_any_rate']:.2%}")
    print(f"downloadable_creative_rate: {summary['downloadable_creative_rate']:.2%}")
    print(f"thumbnail_rate:             {summary['thumbnail_rate']:.2%}")
    print(f"image_rate:                 {summary['image_rate']:.2%}")
    print(f"video_rate:                 {summary['video_rate']:.2%}")
    print(f"destination_rate:           {summary['destination_rate']:.2%}")
    print(f"lp_metadata_rate:           {summary['lp_metadata_rate']:.2%}")
    print(f"lp_content_rate:            {summary['lp_content_rate']:.2%}")
    print(f"full_completion_rate:       {summary['full_completion_rate']:.2%}")

    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(f"report:                     {args.json_report}")


if __name__ == "__main__":
    main()
