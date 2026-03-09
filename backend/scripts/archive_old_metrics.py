"""A62 (CI-065): Data retention policy — archive & purge old metrics.

Moves ad_daily_metrics older than a retention period to a JSON archive,
then optionally deletes them from the database to keep tables lean.

Default retention: 90 days (configurable via --days).

Usage:
    python -m scripts.archive_old_metrics                      # dry-run (default)
    python -m scripts.archive_old_metrics --execute            # actually archive & delete
    python -m scripts.archive_old_metrics --days 180           # keep 180 days
    python -m scripts.archive_old_metrics --archive-dir /path  # custom archive location
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import SyncSessionLocal

DEFAULT_RETENTION_DAYS = 90
DEFAULT_ARCHIVE_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports", "archives"
)
BATCH_SIZE = 1000


def get_archive_stats(session, cutoff_date: date) -> dict:
    """Get counts of records that would be archived."""
    metrics_count = session.execute(text(
        "SELECT COUNT(*) FROM ad_daily_metrics WHERE metric_date < :cutoff"
    ), {"cutoff": cutoff_date}).scalar()

    total_metrics = session.execute(text(
        "SELECT COUNT(*) FROM ad_daily_metrics"
    )).scalar()

    oldest = session.execute(text(
        "SELECT MIN(metric_date) FROM ad_daily_metrics"
    )).scalar()

    return {
        "cutoff_date": str(cutoff_date),
        "to_archive": metrics_count,
        "total_metrics": total_metrics,
        "oldest_record": str(oldest) if oldest else "none",
        "retention_pct": round((total_metrics - metrics_count) / total_metrics * 100, 1) if total_metrics else 0,
    }


def export_archive(session, cutoff_date: date, archive_dir: str) -> str:
    """Export old metrics to a JSON archive file. Returns the file path."""
    os.makedirs(archive_dir, exist_ok=True)

    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    archive_path = os.path.join(archive_dir, f"metrics_archive_{today}_before_{cutoff_date}.json")

    records = []
    offset = 0
    while True:
        rows = session.execute(text("""
            SELECT id, ad_id, metric_date, view_count, view_count_increase,
                   estimated_spend, estimated_spend_increase, like_count,
                   confidence_level, genre, product_name, platform, created_at
            FROM ad_daily_metrics
            WHERE metric_date < :cutoff
            ORDER BY metric_date, ad_id
            LIMIT :limit OFFSET :offset
        """), {"cutoff": cutoff_date, "limit": BATCH_SIZE, "offset": offset}).fetchall()

        if not rows:
            break

        for r in rows:
            records.append({
                "id": r[0],
                "ad_id": r[1],
                "metric_date": str(r[2]),
                "view_count": r[3],
                "view_count_increase": r[4],
                "estimated_spend": float(r[5]) if r[5] else 0,
                "estimated_spend_increase": float(r[6]) if r[6] else 0,
                "like_count": r[7],
                "confidence_level": r[8],
                "genre": r[9],
                "product_name": r[10],
                "platform": r[11],
                "created_at": str(r[12]) if r[12] else None,
            })
        offset += BATCH_SIZE

    with open(archive_path, "w", encoding="utf-8") as f:
        json.dump({
            "archived_at": datetime.now(timezone.utc).isoformat(),
            "cutoff_date": str(cutoff_date),
            "record_count": len(records),
            "records": records,
        }, f, ensure_ascii=False, indent=2)

    return archive_path


def purge_old_metrics(session, cutoff_date: date) -> int:
    """Delete archived metrics from the database. Returns count deleted."""
    result = session.execute(text(
        "DELETE FROM ad_daily_metrics WHERE metric_date < :cutoff"
    ), {"cutoff": cutoff_date})
    session.commit()
    return result.rowcount


def main():
    parser = argparse.ArgumentParser(description="Archive & purge old metrics")
    parser.add_argument("--days", type=int, default=DEFAULT_RETENTION_DAYS,
                        help=f"Retention period in days (default: {DEFAULT_RETENTION_DAYS})")
    parser.add_argument("--archive-dir", default=DEFAULT_ARCHIVE_DIR,
                        help=f"Archive directory (default: {DEFAULT_ARCHIVE_DIR})")
    parser.add_argument("--execute", action="store_true",
                        help="Actually archive and delete (default: dry-run)")
    parser.add_argument("--skip-archive", action="store_true",
                        help="Delete without archiving (use with caution)")
    args = parser.parse_args()

    cutoff_date = date.today() - timedelta(days=args.days)

    print("=" * 60)
    print("  Data Retention: Archive & Purge")
    print("=" * 60)
    print(f"  Retention: {args.days} days")
    print(f"  Cutoff:    {cutoff_date}")
    print(f"  Mode:      {'EXECUTE' if args.execute else 'DRY-RUN'}")

    session = SyncSessionLocal()
    try:
        stats = get_archive_stats(session, cutoff_date)

        print(f"\n  Oldest record:     {stats['oldest_record']}")
        print(f"  Total metrics:     {stats['total_metrics']}")
        print(f"  To archive:        {stats['to_archive']}")
        print(f"  Retained:          {stats['retention_pct']}%")

        if stats["to_archive"] == 0:
            print("\n  Nothing to archive. All records within retention window.")
            return

        if not args.execute:
            print("\n  DRY-RUN: No changes made. Use --execute to proceed.")
            return

        # Step 1: Archive to JSON
        if not args.skip_archive:
            print("\n  Archiving to JSON...")
            archive_path = export_archive(session, cutoff_date, args.archive_dir)
            archive_size = os.path.getsize(archive_path) / 1024
            print(f"  Archived: {archive_path} ({archive_size:.1f} KB)")

        # Step 2: Purge from DB
        print("  Purging from database...")
        deleted = purge_old_metrics(session, cutoff_date)
        print(f"  Deleted: {deleted} rows")

        print("\n  Done!")

    except Exception as e:
        print(f"\n  ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
