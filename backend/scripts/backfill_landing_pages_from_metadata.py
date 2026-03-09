"""Backfill landing_pages rows from existing ads.metadata LP payloads.

Use when LP data already exists in `ads.metadata.lp_info` / `lp_data` but the
normalized `landing_pages` table is empty or missing rows.

Run from the backend directory:
    python scripts/backfill_landing_pages_from_metadata.py
"""

from __future__ import annotations

import hashlib
import os
import sys
from datetime import datetime, timezone
from urllib.parse import urlparse

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.database import SyncSessionLocal, is_in_memory_mode
from app.models.ad import Ad
from app.models.landing_page import LandingPage, LPStatusEnum, LPTypeEnum


def _get_session() -> Session:
    if not is_in_memory_mode():
        return SyncSessionLocal()
    db_path = os.path.join(BASE_DIR, "vaap_local.db")
    if not os.path.exists(db_path):
        raise RuntimeError(f"vaap_local.db not found at {db_path}")
    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    return sessionmaker(bind=engine)()


def _parse_dt(raw: object) -> datetime | None:
    if raw in (None, ""):
        return None
    if isinstance(raw, datetime):
        return raw if raw.tzinfo else raw.replace(tzinfo=timezone.utc)
    text = str(raw).strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _map_lp_type(value: object) -> LPTypeEnum:
    raw = str(value or "").strip().lower()
    if raw in {"article_lp", "article"}:
        return LPTypeEnum.ARTICLE
    if raw in {"ec_site", "ec_direct", "ec"}:
        return LPTypeEnum.EC_DIRECT
    if raw in {"lead_gen", "lead", "survey_lp"}:
        return LPTypeEnum.LEAD_GEN
    if raw in {"app_download", "app_store"}:
        return LPTypeEnum.APP_STORE
    if raw in {"official_site", "brand"}:
        return LPTypeEnum.BRAND
    return LPTypeEnum.OTHER


def _ad_lp_payload(ad: Ad) -> dict:
    meta = ad.ad_metadata or {}
    lp_info = meta.get("lp_info") if isinstance(meta.get("lp_info"), dict) else {}
    lp_data = meta.get("lp_data") if isinstance(meta.get("lp_data"), dict) else {}
    payload = {
        "url": ad.destination_url or lp_info.get("final_url") or lp_data.get("final_url") or "",
        "final_url": lp_info.get("final_url") or lp_data.get("final_url") or ad.destination_url or "",
        "title": lp_info.get("title") or lp_data.get("title") or "",
        "meta_description": lp_info.get("description") or lp_data.get("meta_description") or lp_data.get("description") or "",
        "og_image_url": lp_info.get("og_image") or lp_data.get("og_image") or "",
        "canonical": lp_info.get("canonical") or lp_data.get("canonical_url") or "",
        "http_status": lp_info.get("http_status") or lp_data.get("status_code"),
        "destination_type": lp_data.get("destination_type") or meta.get("destination_type") or "",
        "crawled_at": lp_info.get("fetched_at") or lp_data.get("crawled_at") or meta.get("lp_snapshot_at"),
        "full_text": lp_data.get("full_text_content") or lp_data.get("text_content") or "",
    }
    return payload


def backfill_landing_pages(session: Session) -> dict[str, int]:
    stats = {
        "ads_scanned": 0,
        "eligible_ads": 0,
        "created": 0,
        "updated": 0,
        "skipped_no_lp": 0,
    }
    ads = session.query(Ad).all()
    for ad in ads:
        stats["ads_scanned"] += 1
        payload = _ad_lp_payload(ad)
        target_url = str(payload["url"] or payload["final_url"]).strip()
        if not target_url:
            stats["skipped_no_lp"] += 1
            continue
        stats["eligible_ads"] += 1
        url_hash = hashlib.sha256(target_url.encode("utf-8")).hexdigest()
        lp = session.query(LandingPage).filter(LandingPage.url_hash == url_hash).first()
        if lp is None:
            lp = LandingPage(url=target_url, url_hash=url_hash)
            session.add(lp)
            stats["created"] += 1
        else:
            stats["updated"] += 1

        final_url = str(payload["final_url"] or target_url).strip()
        parsed = urlparse(final_url)
        domain = parsed.netloc.lower().replace("www.", "") if parsed.netloc else None

        lp.ad_id = ad.id
        lp.final_url = final_url
        lp.domain = domain
        lp.title = str(payload["title"] or "")[:500] or None
        lp.meta_description = str(payload["meta_description"] or "") or None
        lp.og_image_url = str(payload["og_image_url"] or "") or None
        lp.genre = getattr(ad.category, "value", None) if getattr(ad, "category", None) else None
        lp.advertiser_name = ad.advertiser_name
        lp.product_name = str((ad.ad_metadata or {}).get("product_name") or (ad.ad_metadata or {}).get("product_category") or "") or None
        lp.lp_type = _map_lp_type(payload["destination_type"])
        lp.status = LPStatusEnum.COMPLETED
        lp.crawled_at = _parse_dt(payload["crawled_at"]) or datetime.now(timezone.utc)
        if payload["full_text"]:
            lp.full_text_content = str(payload["full_text"])[:50000]
        lp.lp_metadata = {
            "canonical": payload["canonical"],
            "http_status": payload["http_status"],
            "source": "ads_metadata_backfill",
            "destination_type": payload["destination_type"],
        }
    session.commit()
    return stats


def main() -> None:
    session = _get_session()
    try:
        stats = backfill_landing_pages(session)
        print("landing_pages_backfill", stats)
    finally:
        session.close()


if __name__ == "__main__":
    main()
