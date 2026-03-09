"""Recover missing creative assets and LP content for existing ads.

Usage:
    python -m scripts.recover_creative_lp_completeness --thumb-limit 100 --lp-limit 100
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import or_

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, MediaExtractionStatus
from app.tasks import crawl_tasks, lp_tasks, media_tasks


def _materialize_still_images(session, limit: int) -> dict:
    if limit <= 0:
        return {"scanned": 0, "completed": 0, "failed": 0, "ids": []}

    ads = (
        session.query(Ad)
        .filter(
            or_(Ad.thumbnail_url.isnot(None), Ad.image_url.isnot(None)),
            or_(Ad.thumbnail_s3_key.is_(None), Ad.image_s3_key.is_(None)),
            Ad.media_extraction_status.in_([
                MediaExtractionStatus.SKIPPED,
                MediaExtractionStatus.ENRICHED,
                MediaExtractionStatus.PENDING,
                MediaExtractionStatus.PENDING_HEAVY,
            ]),
        )
        .order_by(Ad.created_at.desc(), Ad.id.desc())
        .limit(limit)
        .all()
    )

    completed = 0
    failed = 0
    completed_ids: list[int] = []
    for ad in ads:
        result = media_tasks.download_thumbnail_task.run(ad_id=ad.id)
        if result.get("status") == "completed":
            completed += 1
            completed_ids.append(int(ad.id))
        elif result.get("status") == "failed":
            failed += 1
    return {"scanned": len(ads), "completed": completed, "failed": failed, "ids": completed_ids}


def _recover_media_assets(session, limit: int) -> dict:
    if limit <= 0:
        return {"scanned": 0, "completed": 0, "enriched": 0, "failed": 0, "ids": []}

    ads = (
        session.query(Ad)
        .filter(
            Ad.snapshot_url.isnot(None),
            Ad.snapshot_url != "",
            or_(
                Ad.thumbnail_s3_key.is_(None),
                Ad.image_s3_key.is_(None),
                Ad.video_s3_key.is_(None),
                Ad.s3_key.is_(None),
            ),
            Ad.media_extraction_status.in_([
                MediaExtractionStatus.PENDING,
                MediaExtractionStatus.PENDING_HEAVY,
                MediaExtractionStatus.FAILED,
                MediaExtractionStatus.ENRICHED,
                MediaExtractionStatus.SKIPPED,
                MediaExtractionStatus.RETRYING,
            ]),
        )
        .order_by(Ad.created_at.desc(), Ad.id.desc())
        .limit(limit)
        .all()
    )

    completed = 0
    enriched = 0
    failed = 0
    recovered_ids: list[int] = []
    for ad in ads:
        result = media_tasks.extract_media_task.run(ad_id=ad.id, use_playwright=True)
        status = str(result.get("status") or "")
        if status == "completed":
            completed += 1
            recovered_ids.append(int(ad.id))
        elif status == "enriched":
            enriched += 1
            recovered_ids.append(int(ad.id))
        else:
            failed += 1
    return {
        "scanned": len(ads),
        "completed": completed,
        "enriched": enriched,
        "failed": failed,
        "ids": recovered_ids,
    }


def _recover_lp_content(session, limit: int, auto_analyze: bool) -> dict:
    if limit <= 0:
        return {"scanned": 0, "completed": 0, "failed": 0, "ids": []}

    candidates = (
        session.query(Ad)
        .filter(Ad.destination_url.isnot(None), Ad.destination_url != "")
        .order_by(Ad.created_at.desc(), Ad.id.desc())
        .limit(limit * 4)
        .all()
    )

    grouped: dict[str, list[Ad]] = defaultdict(list)
    for ad in candidates:
        if not crawl_tasks._needs_lp_enrichment(ad):
            continue
        grouped[str(ad.destination_url)].append(ad)

    completed = 0
    failed = 0
    completed_ids: list[int] = []
    scanned = 0
    for url, ads_for_url in grouped.items():
        if completed + failed >= limit:
            break

        reused_ids: list[int] = []
        for ad in ads_for_url:
            if completed + failed >= limit:
                break
            if lp_tasks.reuse_existing_lp_for_ad(session, ad_id=int(ad.id), url=url):
                completed += 1
                completed_ids.append(int(ad.id))
                reused_ids.append(int(ad.id))

        remaining_ads = [ad for ad in ads_for_url if int(ad.id) not in set(reused_ids)]
        if not remaining_ads or completed + failed >= limit:
            continue

        scanned += 1
        ad = remaining_ads[0]
        result = lp_tasks.crawl_and_analyze_lp_task.run(
            url=url,
            ad_id=ad.id,
            genre=getattr(getattr(ad, "category", None), "value", None),
            product_name=str((ad.ad_metadata or {}).get("product_name") or (ad.ad_metadata or {}).get("product_category") or "") or None,
            advertiser_name=ad.advertiser_name,
            auto_analyze=auto_analyze,
        )
        if result.get("status") == "completed":
            completed += 1
            completed_ids.append(int(ad.id))
            for sibling in remaining_ads[1:]:
                if completed + failed >= limit:
                    break
                if lp_tasks.reuse_existing_lp_for_ad(session, ad_id=int(sibling.id), url=url):
                    completed += 1
                    completed_ids.append(int(sibling.id))
        else:
            failed += 1
    return {"scanned": scanned, "completed": completed, "failed": failed, "ids": completed_ids}


def _recover_missing_destination_terminal(session, limit: int) -> dict:
    if limit <= 0:
        return {"scanned": 0, "completed": 0, "failed": 0, "ids": []}

    ads = (
        session.query(Ad)
        .filter(or_(Ad.destination_url.is_(None), Ad.destination_url == ""))
        .order_by(Ad.created_at.desc(), Ad.id.desc())
        .limit(limit)
        .all()
    )

    completed = 0
    completed_ids: list[int] = []
    for ad in ads:
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
        if meta.get("lp_terminal") and meta.get("lp_fetch_error_code") == "no_destination_url":
            continue
        lp_tasks._sync_lp_failure_to_ad(
            session,
            ad_id=int(ad.id),
            url="",
            status="missing_destination",
            error_code="no_destination_url",
            error_message="No destination URL was available in the source ad metadata.",
        )
        completed += 1
        completed_ids.append(int(ad.id))

    return {"scanned": len(ads), "completed": completed, "failed": 0, "ids": completed_ids}


def main() -> None:
    parser = argparse.ArgumentParser(description="Recover missing creative/LP completeness")
    parser.add_argument("--media-limit", type=int, default=50)
    parser.add_argument("--thumb-limit", type=int, default=50)
    parser.add_argument("--lp-limit", type=int, default=50)
    parser.add_argument("--terminal-limit", type=int, default=50)
    parser.add_argument("--auto-analyze", action="store_true")
    args = parser.parse_args()

    session = SyncSessionLocal()
    try:
        media = _recover_media_assets(session, args.media_limit)
        thumb = _materialize_still_images(session, args.thumb_limit)
        lp = _recover_lp_content(session, args.lp_limit, args.auto_analyze)
        terminal = _recover_missing_destination_terminal(session, args.terminal_limit)
        print(
            "recovery_run",
            {
                "ran_at": datetime.now(timezone.utc).isoformat(),
                "media": media,
                "thumb": thumb,
                "lp": lp,
                "terminal": terminal,
            },
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
