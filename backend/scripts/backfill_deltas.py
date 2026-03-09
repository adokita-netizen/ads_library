"""A-R2-2: Backfill daily metrics deltas.

Recalculates view_count_increase and estimated_spend_increase for all
existing AdDailyMetrics rows based on the previous day's cumulative values.

Ensures ProRankingTable displays correct delta columns.

Usage:
    python -m scripts.backfill_deltas              # dry-run (count only)
    python -m scripts.backfill_deltas --execute    # apply changes
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.ad_metrics import AdDailyMetrics


BATCH_SIZE = 100


def backfill_deltas(session, execute: bool = False) -> dict:
    """Recalculate deltas for all metrics rows."""
    total_ads = session.query(Ad.id).count()
    offset = 0
    total_updated = 0
    total_rows = 0

    while True:
        ad_ids = [r[0] for r in session.query(Ad.id).order_by(Ad.id).offset(offset).limit(BATCH_SIZE).all()]
        if not ad_ids:
            break

        for ad_id in ad_ids:
            metrics = (
                session.query(AdDailyMetrics)
                .filter(AdDailyMetrics.ad_id == ad_id)
                .order_by(AdDailyMetrics.metric_date.asc())
                .all()
            )

            total_rows += len(metrics)

            for i, m in enumerate(metrics):
                if i == 0:
                    # First record: delta = cumulative value
                    new_view_inc = m.view_count or 0
                    new_spend_inc = float(m.estimated_spend or 0)
                else:
                    prev = metrics[i - 1]
                    new_view_inc = max(0, (m.view_count or 0) - (prev.view_count or 0))
                    new_spend_inc = max(0.0, float(m.estimated_spend or 0) - float(prev.estimated_spend or 0))

                if m.view_count_increase != new_view_inc or abs((m.estimated_spend_increase or 0) - new_spend_inc) > 0.01:
                    if execute:
                        m.view_count_increase = new_view_inc
                        m.estimated_spend_increase = round(new_spend_inc, 2)
                    total_updated += 1

        if execute:
            session.flush()

        offset += BATCH_SIZE

    if execute:
        session.commit()

    return {
        "total_ads": total_ads,
        "total_metric_rows": total_rows,
        "rows_needing_update": total_updated,
        "executed": execute,
    }


def main():
    parser = argparse.ArgumentParser(description="Backfill metrics deltas")
    parser.add_argument("--execute", action="store_true", help="Apply changes (default: dry-run)")
    args = parser.parse_args()

    print("=" * 60)
    print("  A-R2-2: Backfill Daily Metrics Deltas")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        result = backfill_deltas(session, execute=args.execute)

        print(f"\n  Total ads: {result['total_ads']}")
        print(f"  Total metric rows: {result['total_metric_rows']}")
        print(f"  Rows needing update: {result['rows_needing_update']}")

        if not args.execute:
            print("\n  DRY-RUN. Use --execute to apply.")
        else:
            print("\n  Changes committed.")

        print()

    except Exception as e:
        session.rollback()
        print(f"\n  ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
