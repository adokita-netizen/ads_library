"""Populate ad_analyses with winning_score for all ads.

Uses the existing compute_hit_score logic from ranking_service.
Creates ad_analyses rows where they don't exist yet.
"""
import os
import sys
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")


def compute_hit_score_standalone(row: dict) -> tuple[float, str, dict]:
    """Simplified hit score computation using raw DB values.

    Scoring (0-100):
      1. Longevity (0-40): days between first_seen and last_seen
      2. Spend (0-20): total ad spend
      3. Active bonus (0-20): still running or long-lived
      4. Creative quality (0-10): has video/image/thumbnail
      5. View engagement (0-10): view_count relative to spend
    """
    signals = {}

    # Days running
    days_running = 0
    if row["first_seen_at"]:
        try:
            first = datetime.fromisoformat(row["first_seen_at"].replace("Z", "+00:00"))
            if first.tzinfo is None:
                first = first.replace(tzinfo=timezone.utc)
            if row["last_seen_at"]:
                last = datetime.fromisoformat(row["last_seen_at"].replace("Z", "+00:00"))
                if last.tzinfo is None:
                    last = last.replace(tzinfo=timezone.utc)
            else:
                last = datetime.now(timezone.utc)
            days_running = max(1, (last - first).days)
        except (ValueError, TypeError):
            days_running = 1

    # Signal 1: Longevity (0-40)
    if days_running >= 120:
        longevity = 40.0
    elif days_running >= 90:
        longevity = 35 + (days_running - 90) / 30 * 5
    elif days_running >= 60:
        longevity = 25 + (days_running - 60) / 30 * 10
    elif days_running >= 30:
        longevity = 15 + (days_running - 30) / 30 * 10
    elif days_running >= 14:
        longevity = 5 + (days_running - 14) / 16 * 10
    else:
        longevity = days_running / 14 * 5
    signals["longevity"] = round(longevity, 1)

    # Signal 2: Spend (0-20)
    spend = row.get("spend") or 0
    if spend >= 5_000_000:
        spend_score = 20.0
    elif spend >= 1_000_000:
        spend_score = 12 + (spend - 1_000_000) / 4_000_000 * 8
    elif spend >= 100_000:
        spend_score = 5 + (spend - 100_000) / 900_000 * 7
    elif spend >= 10_000:
        spend_score = 1 + (spend - 10_000) / 90_000 * 4
    else:
        spend_score = spend / 10_000
    signals["spend"] = round(spend_score, 1)

    # Signal 3: Active bonus (0-20)
    is_still_running = row["last_seen_at"] is None
    if is_still_running:
        active_bonus = min(20.0, 10 + days_running / 30 * 10)
    elif days_running >= 60:
        active_bonus = 8.0
    elif days_running >= 30:
        active_bonus = 4.0
    else:
        active_bonus = 0.0
    signals["active_bonus"] = round(active_bonus, 1)

    # Signal 4: Creative quality (0-10)
    creative_score = 0.0
    ctype = row.get("creative_type") or "unknown"
    if ctype == "video":
        creative_score += 5.0
    elif ctype == "image":
        creative_score += 3.0
    if row.get("thumbnail_s3_key") or row.get("thumbnail_url"):
        creative_score += 2.0
    if row.get("image_s3_key") or row.get("image_url"):
        creative_score += 2.0
    if row.get("video_s3_key") or row.get("video_url"):
        creative_score += 1.0
    creative_score = min(10.0, creative_score)
    signals["creative"] = round(creative_score, 1)

    # Signal 5: View engagement (0-10)
    views = row.get("view_count") or 0
    if views >= 1_000_000:
        view_score = 10.0
    elif views >= 100_000:
        view_score = 5 + (views - 100_000) / 900_000 * 5
    elif views >= 10_000:
        view_score = 2 + (views - 10_000) / 90_000 * 3
    elif views > 0:
        view_score = views / 10_000 * 2
    else:
        view_score = 0.0
    signals["trend"] = round(view_score, 1)

    total = sum(signals.values())
    total = min(100.0, round(total, 1))

    if total >= 60:
        level = "mega_hit"
    elif total >= 40:
        level = "hit"
    elif total >= 25:
        level = "promising"
    else:
        level = "normal"

    return total, level, signals


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Get all ads
    cur.execute("""
        SELECT id, title, view_count, like_count, spend, impressions,
               estimated_impressions, estimated_ctr, estimated_cvr,
               first_seen_at, last_seen_at, creative_type,
               thumbnail_url, thumbnail_s3_key, image_url, image_s3_key,
               video_url, video_s3_key, platform
        FROM ads
    """)
    ads = [dict(r) for r in cur.fetchall()]

    # Check existing ad_analyses
    cur.execute("SELECT ad_id FROM ad_analyses")
    existing = {r[0] for r in cur.fetchall()}

    inserted = 0
    updated = 0

    for ad in ads:
        score, level, signals = compute_hit_score_standalone(ad)
        ad_id = ad["id"]

        if ad_id in existing:
            cur.execute(
                "UPDATE ad_analyses SET winning_score = ? WHERE ad_id = ?",
                (score, ad_id),
            )
            updated += 1
        else:
            cur.execute(
                """INSERT INTO ad_analyses (ad_id, winning_score, created_at)
                   VALUES (?, ?, ?)""",
                (ad_id, score, datetime.now(timezone.utc).isoformat()),
            )
            inserted += 1

    conn.commit()

    # Stats
    cur.execute("SELECT COUNT(*) FROM ad_analyses")
    total = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ad_analyses WHERE winning_score IS NOT NULL")
    scored = cur.fetchone()[0]
    cur.execute("SELECT MIN(winning_score), MAX(winning_score), AVG(winning_score) FROM ad_analyses")
    stats = cur.fetchone()
    cur.execute("""
        SELECT
            CASE
                WHEN winning_score >= 60 THEN 'mega_hit'
                WHEN winning_score >= 40 THEN 'hit'
                WHEN winning_score >= 25 THEN 'promising'
                ELSE 'normal'
            END as level,
            COUNT(*) as cnt
        FROM ad_analyses
        GROUP BY level
        ORDER BY cnt DESC
    """)
    levels = cur.fetchall()

    # Top 20
    cur.execute("""
        SELECT a.winning_score, ads.id, ads.title, ads.view_count, ads.spend, ads.creative_type, ads.platform
        FROM ad_analyses a
        JOIN ads ON a.ad_id = ads.id
        ORDER BY a.winning_score DESC
        LIMIT 20
    """)
    top20 = cur.fetchall()

    conn.close()

    print(f"Inserted: {inserted}, Updated: {updated}, Total: {total}")
    print(f"Score stats: min={stats[0]}, max={stats[1]}, avg={stats[2]:.1f}")
    print(f"Level distribution: {levels}")
    print(f"\nTop 20 Hit Ads:")
    for r in top20:
        try:
            title = (r[2] or "")[:40]
            print(f"  Score={r[0]:5.1f} | ID={r[1]:4d} | {r[5]:6s} | {r[6]:10s} | views={r[3]:>10,} | spend={r[4]:>12,.0f} | {title}")
        except (UnicodeEncodeError, TypeError):
            print(f"  Score={r[0]:5.1f} | ID={r[1]:4d} | views={r[3]:>10,} | spend={r[4]:>12,.0f}")


if __name__ == "__main__":
    main()
