"""Recover missing static-image assets for Japanese ads only.

Targets Japanese ads whose creative_type is image/banner/static and that still
lack image/thumbnail cache. Reuses aggressive recovery phases that work from
snapshot/destination URLs.

Run from repo root:
    python backend/scripts/recover_jp_static_media.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import SyncSessionLocal, is_in_memory_mode
from app.models.ad import Ad
from scripts.aggressive_media_recovery import (
    ensure_dirs,
    phase3_snapshot_og_image,
    phase4_playwright_screenshot,
)

JP_RE = re.compile(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]")
LATIN_RE = re.compile(r"[A-Za-z]")
STATIC_TYPES = {"image", "banner", "static"}


def _get_session() -> Session:
    if not is_in_memory_mode():
        return SyncSessionLocal()
    db_path = os.path.join(BASE_DIR, "vaap_local.db")
    if not os.path.exists(db_path):
        raise RuntimeError(f"vaap_local.db not found at {db_path}")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return sessionmaker(bind=engine)()


def _is_japanese_text(text: str | None) -> bool:
    raw = str(text or "").strip()
    if not raw:
        return False
    jp_count = len(JP_RE.findall(raw))
    if jp_count == 0:
        return False
    latin_count = len(LATIN_RE.findall(raw))
    if latin_count == 0:
        return True
    return (jp_count / (jp_count + latin_count)) >= 0.1


def _is_japanese_ad(ad: Ad) -> bool:
    meta = dict(ad.ad_metadata or {})
    lang = str(meta.get("language") or "").strip().lower().replace("_", "-")
    if lang:
        return lang in {"ja", "ja-jp", "jp", "japanese"} or lang.startswith("ja-")
    text = " ".join(
        filter(
            None,
            [
                ad.title,
                ad.description,
                ad.advertiser_name,
                ad.brand_name,
            ],
        )
    )
    return _is_japanese_text(text)


def _target_ads(session: Session, limit: int | None = None) -> list[Ad]:
    ads = (
        session.query(Ad)
        .filter(
            Ad.image_s3_key.is_(None),
            Ad.thumbnail_s3_key.is_(None),
        )
        .order_by(Ad.id)
        .all()
    )
    filtered: list[Ad] = []
    for ad in ads:
        creative_type = str(ad.creative_type or "").strip().lower()
        if creative_type not in STATIC_TYPES:
            continue
        if not _is_japanese_ad(ad):
            continue
        if ad.image_url or ad.thumbnail_url:
            continue
        if not (ad.snapshot_url or ad.destination_url):
            continue
        filtered.append(ad)
        if limit and len(filtered) >= limit:
            break
    return filtered


def main(limit: int | None = None) -> None:
    ensure_dirs()
    session = _get_session()
    try:
        targets = _target_ads(session, limit=limit)
        print("jp_static_missing_targets", len(targets))
        if not targets:
            return

        before = Counter()
        for ad in targets:
            if ad.image_s3_key:
                before["image_s3"] += 1
            if ad.thumbnail_s3_key:
                before["thumb_s3"] += 1
            before[str(ad.media_extraction_status or "null")] += 1
        print("before_status", dict(before))

        recovered_ids: set[int] = set()
        p3_count, p3_ids = phase3_snapshot_og_image(session, targets, recovered_ids)
        recovered_ids.update(p3_ids)
        p4_count, p4_ids = phase4_playwright_screenshot(session, targets, recovered_ids)
        recovered_ids.update(p4_ids)

        after = Counter()
        sample_remaining: list[dict] = []
        for ad in targets:
            session.refresh(ad)
            after[str(ad.media_extraction_status or "null")] += 1
            if ad.thumbnail_s3_key:
                after["thumb_s3"] += 1
            if ad.image_s3_key:
                after["image_s3"] += 1
            if not (ad.thumbnail_s3_key or ad.image_s3_key) and len(sample_remaining) < 10:
                sample_remaining.append(
                    {
                        "id": ad.id,
                        "title": (ad.title or "")[:80],
                        "snapshot": bool(ad.snapshot_url),
                        "destination": bool(ad.destination_url),
                        "status": ad.media_extraction_status,
                        "meta_reason": str((ad.ad_metadata or {}).get("creative_fetch_reason") or ""),
                    }
                )

        print("recovered", {"phase3": p3_count, "phase4": p4_count, "total": len(recovered_ids)})
        print("after_status", dict(after))
        print("remaining_samples", json.dumps(sample_remaining, ensure_ascii=False))
    finally:
        session.close()


if __name__ == "__main__":
    raw_limit = os.getenv("JP_STATIC_MEDIA_LIMIT", "").strip()
    limit = int(raw_limit) if raw_limit else None
    main(limit=limit)
