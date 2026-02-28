#!/usr/bin/env python3
"""Competitor matrix builder: rank advertisers by genre.

For each genre:
  - Rank advertisers by ad count, hit rate, avg score
  - Identify "dominant players" per genre (top 3)
  - Build cross-genre overlap matrix

Exports to backend/exports/competitor_matrix.json

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/build_competitor_matrix.py
"""

import json
import os
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from statistics import mean

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


EXPORTS_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "exports",
)


def _get_score(ad: Ad) -> float:
    """Get hit score from ad_metadata, default 0."""
    try:
        return float((ad.ad_metadata or {}).get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        return 0.0


def _is_hit(ad: Ad) -> bool:
    """Check if ad is a hit or mega_hit."""
    return (ad.ad_metadata or {}).get("hit_level", "none") in ("hit", "mega_hit")


def _safe_mean(values: list[float]) -> float:
    """Return mean or 0 if empty."""
    return round(mean(values), 1) if values else 0.0


def _get_genre(ad: Ad) -> str:
    """Get genre/category for an ad."""
    if ad.category:
        return str(ad.category.value)
    return "other"


def main() -> None:
    print("=" * 60)
    print("COMPETITOR MATRIX BUILDER")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"Total ads in database: {total}")

        if total == 0:
            print("No ads found. Exiting.")
            return

        # ── Step 1: Group ads by genre + advertiser ───────────────────
        # genre -> advertiser -> [ads]
        genre_advertiser: dict[str, dict[str, list[Ad]]] = defaultdict(lambda: defaultdict(list))
        # advertiser -> set of genres they're in
        advertiser_genres: dict[str, set[str]] = defaultdict(set)

        for ad in ads:
            name = ad.advertiser_name
            if not name or name.strip() == "":
                continue
            genre = _get_genre(ad)
            genre_advertiser[genre][name].append(ad)
            advertiser_genres[name].add(genre)

        print(f"Genres: {len(genre_advertiser)}")
        print(f"Advertisers with name: {len(advertiser_genres)}")

        # ── Step 2: Build per-genre rankings ──────────────────────────
        genre_rankings = {}

        for genre, advertisers in sorted(genre_advertiser.items()):
            rankings = []
            for adv_name, adv_ads in advertisers.items():
                ad_count = len(adv_ads)
                hit_count = sum(1 for a in adv_ads if _is_hit(a))
                hit_rate = round(hit_count / ad_count * 100, 1) if ad_count > 0 else 0.0
                scores = [_get_score(a) for a in adv_ads]
                avg_score = _safe_mean(scores)
                max_score = round(max(scores), 1) if scores else 0.0

                rankings.append({
                    "advertiser": adv_name,
                    "ad_count": ad_count,
                    "hit_count": hit_count,
                    "hit_rate": hit_rate,
                    "avg_score": avg_score,
                    "max_score": max_score,
                })

            # Sort by composite: hit_rate * 0.4 + avg_score * 0.4 + ad_count_normalized * 0.2
            max_ad_count = max(r["ad_count"] for r in rankings) if rankings else 1
            for r in rankings:
                r["composite_rank_score"] = round(
                    r["hit_rate"] * 0.4
                    + r["avg_score"] * 0.4
                    + (r["ad_count"] / max_ad_count * 100) * 0.2,
                    1,
                )

            rankings.sort(key=lambda r: r["composite_rank_score"], reverse=True)

            # Mark top 3 as dominant
            for i, r in enumerate(rankings):
                r["rank"] = i + 1
                r["is_dominant"] = i < 3

            genre_rankings[genre] = rankings

        # ── Step 3: Build cross-genre overlap matrix ──────────────────
        # Find advertisers active in multiple genres
        multi_genre_advertisers = {
            adv: sorted(genres)
            for adv, genres in advertiser_genres.items()
            if len(genres) >= 2
        }

        # Genre overlap matrix: how many advertisers are shared between genres
        all_genres = sorted(genre_advertiser.keys())
        overlap_matrix = {}
        for g1 in all_genres:
            overlap_matrix[g1] = {}
            advs1 = set(genre_advertiser[g1].keys())
            for g2 in all_genres:
                advs2 = set(genre_advertiser[g2].keys())
                overlap_matrix[g1][g2] = len(advs1 & advs2)

        # ── Step 4: Build report ──────────────────────────────────────
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "total_ads": total,
            "total_genres": len(genre_rankings),
            "total_advertisers": len(advertiser_genres),
            "genre_rankings": genre_rankings,
            "dominant_players": {},
            "multi_genre_advertisers": multi_genre_advertisers,
            "genre_overlap_matrix": overlap_matrix,
        }

        # Extract dominant players per genre
        for genre, rankings in genre_rankings.items():
            dominants = [r for r in rankings if r["is_dominant"]]
            report["dominant_players"][genre] = dominants

        # ── Step 5: Export ────────────────────────────────────────────
        os.makedirs(EXPORTS_DIR, exist_ok=True)
        export_path = os.path.join(EXPORTS_DIR, "competitor_matrix.json")
        with open(export_path, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\nExported to: {export_path}")

        # ── Print Summary ────────────────────────────────────────────
        print(f"\n{'=' * 60}")
        print("GENRE RANKINGS SUMMARY")
        print(f"{'=' * 60}")

        for genre in all_genres:
            rankings = genre_rankings.get(genre, [])
            print(f"\n  --- {genre} ({len(rankings)} advertisers) ---")
            print(f"  {'#':>2s} {'Advertiser':<30s} {'Ads':>4s} {'Hits':>4s} {'Rate':>6s} {'AvgSc':>6s} {'Rank':>5s}")
            for r in rankings[:5]:
                adv_safe = r["advertiser"][:28].encode("ascii", "replace").decode("ascii")
                dom = " *" if r["is_dominant"] else ""
                print(
                    f"  {r['rank']:>2d} {adv_safe:<30s} "
                    f"{r['ad_count']:>4d} {r['hit_count']:>4d} "
                    f"{r['hit_rate']:>5.1f}% {r['avg_score']:>5.1f} "
                    f"{r['composite_rank_score']:>5.1f}{dom}"
                )

        # Multi-genre advertisers
        print(f"\n{'=' * 60}")
        print(f"MULTI-GENRE ADVERTISERS ({len(multi_genre_advertisers)})")
        print(f"{'=' * 60}")
        for adv, genres in sorted(multi_genre_advertisers.items(),
                                   key=lambda x: -len(x[1])):
            adv_safe = adv[:30].encode("ascii", "replace").decode("ascii")
            print(f"  {adv_safe:<32s} genres: {', '.join(genres)}")

        # Genre overlap
        if len(all_genres) > 1:
            print(f"\n{'=' * 60}")
            print("GENRE OVERLAP (shared advertisers)")
            print(f"{'=' * 60}")
            header = "         " + "".join(f"{g[:7]:>8s}" for g in all_genres)
            print(header)
            for g1 in all_genres:
                row = f"  {g1[:7]:<7s}"
                for g2 in all_genres:
                    count = overlap_matrix[g1][g2]
                    row += f"{count:>8d}"
                print(row)

        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"FATAL ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
