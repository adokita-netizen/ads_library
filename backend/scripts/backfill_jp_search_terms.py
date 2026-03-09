#!/usr/bin/env python3
"""Backfill Japanese grouped and individual search terms into ad metadata."""

import io
import os
import sys
from collections import defaultdict

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm.attributes import flag_modified

from app.models.ad import Ad
from scripts.batch_crawl_japanese import GENRE_KEYWORDS


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


TARGET_GENRES = {"beauty", "hair_removal", "aga", "diet", "fitness"}


def _append_unique(values: list[str], value: str | None) -> list[str]:
    normalized = str(value or "").strip()
    if not normalized:
        return values
    if normalized not in values:
        values.append(normalized)
    return values


def _collect_candidate_text(meta: dict, ad: Ad) -> str:
    parts = [
        ad.title or "",
        ad.description or "",
        ad.advertiser_name or "",
        str(meta.get("crawl_query") or ""),
        str(meta.get("last_crawl_keyword") or ""),
        str(meta.get("source_keyword") or ""),
    ]
    return "\n".join(parts).lower()


def main() -> None:
    db_path = os.path.join(BASE_DIR, "vaap_local.db")
    engine = create_engine(f"sqlite:///{db_path}")
    session = sessionmaker(bind=engine)()
    updated = 0
    scanned = 0
    by_genre: dict[str, int] = defaultdict(int)

    try:
        ads = session.query(Ad).all()
        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            genre_keys = list(meta.get("jp_genres") or [])
            single_key = str(meta.get("jp_genre_key") or "").strip()
            if single_key and single_key not in genre_keys:
                genre_keys.append(single_key)

            target_keys = [key for key in genre_keys if key in TARGET_GENRES]
            if not target_keys:
                continue

            scanned += 1
            haystack = _collect_candidate_text(meta, ad)
            search_terms = list(meta.get("jp_search_terms", []))
            aliases = list(meta.get("crawl_query_aliases", []))

            _append_unique(search_terms, meta.get("crawl_query"))
            _append_unique(search_terms, meta.get("last_crawl_keyword"))
            _append_unique(search_terms, meta.get("source_keyword"))

            for genre_key in target_keys:
                for keyword in GENRE_KEYWORDS.get(genre_key, {}).get("keywords", []):
                    if keyword.lower() in haystack:
                        _append_unique(search_terms, keyword)

            for term in search_terms:
                _append_unique(aliases, term)

            if search_terms != list(meta.get("jp_search_terms", [])) or aliases != list(meta.get("crawl_query_aliases", [])):
                meta["jp_search_terms"] = search_terms
                meta["crawl_query_aliases"] = aliases
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                updated += 1
                for genre_key in target_keys:
                    by_genre[genre_key] += 1

        session.commit()
        print(
            {
                "scanned": scanned,
                "updated": updated,
                "by_genre": dict(sorted(by_genre.items())),
            }
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
