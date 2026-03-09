"""Refresh product_rankings table with latest hit scores from ad_analyses.

This ensures the /rankings/hit-ads and /rankings/pro-ranking endpoints
return fresh data based on the actual winning_score in ad_analyses.
"""
import os
import sqlite3
import json
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    # Get all ads with their analyses
    cur.execute("""
        SELECT
            a.id, a.title, a.advertiser_name, a.category, a.platform,
            a.view_count, a.spend, a.like_count, a.creative_type,
            a.first_seen_at, a.last_seen_at,
            a.thumbnail_url, a.image_url, a.video_url,
            an.winning_score
        FROM ads a
        LEFT JOIN ad_analyses an ON a.id = an.ad_id
        WHERE an.winning_score IS NOT NULL
        ORDER BY an.winning_score DESC
    """)
    ads = [dict(r) for r in cur.fetchall()]

    if not ads:
        print("No ads with winning scores found.")
        conn.close()
        return

    # Delete old rankings for today
    cur.execute("DELETE FROM product_rankings WHERE period_start = ?", (today,))

    # Insert new rankings
    inserted = 0
    for rank, ad in enumerate(ads, 1):
        score = ad["winning_score"] or 0
        views = ad["view_count"] or 0
        spend = ad["spend"] or 0

        # Determine hit level
        if score >= 60:
            hit_level = "mega_hit"
            is_hit = 1
        elif score >= 40:
            hit_level = "hit"
            is_hit = 1
        elif score >= 25:
            hit_level = "promising"
            is_hit = 0
        else:
            hit_level = "normal"
            is_hit = 0

        # Build metadata
        metadata = json.dumps({
            "hit_level": hit_level,
            "score_breakdown": {},
            "creative_type": ad["creative_type"],
        })

        # Map category to genre name
        genre = ad["category"] or "other"

        cur.execute("""
            INSERT INTO product_rankings (
                period, period_start, period_end, ad_id,
                product_name, advertiser_name, genre, platform,
                rank_position, previous_rank, rank_change,
                total_view_increase, total_spend_increase,
                cumulative_views, cumulative_spend,
                is_hit, hit_score, trend_score,
                metadata, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "daily", today, today, ad["id"],
            ad["title"][:255] if ad["title"] else f"Ad-{ad['id']}",
            ad["advertiser_name"] or "Unknown",
            genre,
            ad["platform"] or "facebook",
            rank,
            None,  # previous_rank
            None,  # rank_change
            views,  # total_view_increase
            spend,  # total_spend_increase
            views,  # cumulative_views
            spend,  # cumulative_spend
            is_hit,
            score,  # hit_score
            min(100, score * 1.1),  # trend_score
            metadata,
            datetime.now(timezone.utc).isoformat(),
        ))
        inserted += 1

    conn.commit()

    # Stats
    cur.execute("SELECT COUNT(*) FROM product_rankings WHERE period_start = ?", (today,))
    today_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM product_rankings WHERE is_hit = 1 AND period_start = ?", (today,))
    hit_count = cur.fetchone()[0]

    conn.close()

    print(f"Inserted {inserted} rankings for {today}")
    print(f"  Total rankings today: {today_count}")
    print(f"  Hit ads: {hit_count}")
    print(f"  Top 10:")
    # Re-read top 10
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("""
        SELECT rank_position, ad_id, product_name, hit_score, cumulative_views, is_hit
        FROM product_rankings
        WHERE period_start = ?
        ORDER BY rank_position
        LIMIT 10
    """, (today,))
    for r in cur.fetchall():
        try:
            name = (r[2] or "")[:50]
            print(f"    #{r[0]:3d} | ID={r[1]:4d} | score={r[3]:5.1f} | views={r[4]:>10,} | hit={r[5]} | {name}")
        except (UnicodeEncodeError, TypeError):
            print(f"    #{r[0]:3d} | ID={r[1]:4d} | score={r[3]:5.1f} | views={r[4]:>10,}")
    conn.close()


if __name__ == "__main__":
    main()
