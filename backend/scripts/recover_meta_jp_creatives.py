#!/usr/bin/env python3
"""Recover missing creatives for Japanese Meta ads using existing inline enrich helpers."""

from __future__ import annotations

import os
import sys

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from app.models.ad import Ad, AdPlatformEnum
from app.tasks.crawl_tasks import _inline_download_thumbnail, _inline_enrich


def _get_session():
    db_path = os.path.join(BASE_DIR, "vaap_local.db")
    engine = create_engine(f"sqlite:///{db_path}")
    Session = sessionmaker(bind=engine, expire_on_commit=False)
    return Session()


def _is_japanese_meta(ad: Ad) -> bool:
    meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
    ratio = float(meta.get("jp_char_ratio") or meta.get("japanese_ratio") or 0.0)
    langs = meta.get("languages") or []
    if isinstance(langs, str):
        langs = [langs]
    langs_norm = [str(v).lower() for v in langs]
    return ratio >= 0.05 or any(v == "ja" or v.startswith("ja-") or v.startswith("ja_") for v in langs_norm)


def main() -> None:
    limit = int(os.getenv("META_CREATIVE_RECOVERY_LIMIT", "120"))
    rounds = int(os.getenv("META_CREATIVE_RECOVERY_ROUNDS", "1"))
    session = _get_session()
    try:
        def _missing_candidates(rows):
            picked = []
            for item in rows:
                if not _is_japanese_meta(item):
                    continue
                has_creative = bool(
                    item.thumbnail_url
                    or item.image_url
                    or item.video_url
                    or item.thumbnail_s3_key
                    or item.image_s3_key
                    or item.s3_key
                )
                if has_creative:
                    continue
                if not (item.snapshot_url or item.external_id):
                    continue
                picked.append(item)
            return picked

        attempted = 0
        recovered = 0
        round_results = []

        def _all_targets():
            return (
                session.query(Ad)
                .filter(Ad.platform.in_([AdPlatformEnum.FACEBOOK, AdPlatformEnum.INSTAGRAM]))
                .order_by(Ad.updated_at.desc(), Ad.id.desc())
                .all()
            )

        before_missing = _missing_candidates(_all_targets())
        for round_index in range(rounds):
            candidates = _missing_candidates(_all_targets())[:limit]
            if not candidates:
                round_results.append({"round": round_index + 1, "attempted": 0, "recovered": 0, "remaining": 0})
                break

            attempted_this_round = 0
            before_ids = {ad.id for ad in candidates}
            for ad in candidates:
                attempted += 1
                attempted_this_round += 1
                try:
                    _inline_enrich(ad, session)
                except Exception:
                    session.rollback()
                if not (ad.thumbnail_s3_key or ad.image_s3_key):
                    try:
                        _inline_download_thumbnail(ad, session)
                    except Exception:
                        session.rollback()

            session.expire_all()
            remaining_candidates = _missing_candidates(_all_targets())
            remaining_ids = {ad.id for ad in remaining_candidates}
            recovered_this_round = len(before_ids - remaining_ids)
            recovered += recovered_this_round
            round_results.append(
                {
                    "round": round_index + 1,
                    "attempted": attempted_this_round,
                    "recovered": recovered_this_round,
                    "remaining": len(remaining_candidates),
                }
            )
            if recovered_this_round == 0:
                break

        remaining = len(_missing_candidates(_all_targets()))
        recovered = max(recovered, len(before_missing) - remaining)

        print(
            {
                "attempted": attempted,
                "recovered": recovered,
                "remaining_missing_creative": remaining,
                "rounds": round_results,
            }
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
