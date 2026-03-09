"""A66 (CI-073): Metric anomaly detection rules.

Detects unusual patterns in ad_daily_metrics:
  - Sudden spikes in view_count_increase (>5x 7-day average)
  - Sudden drops (view_count_increase = 0 for previously active ads)
  - Negative values in spend or views
  - Outlier estimated_spend (>3 std deviations from platform mean)
  - Stale ads with no metrics for >3 days

Usage:
    python -m scripts.detect_metric_anomalies
    python -m scripts.detect_metric_anomalies --json-report exports/anomalies.json
    python -m scripts.detect_metric_anomalies --days 7  # look back 7 days
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import SyncSessionLocal


DEFAULT_LOOKBACK_DAYS = 7
SPIKE_MULTIPLIER = 5.0  # flag if >5x the 7-day moving average
STALE_THRESHOLD_DAYS = 3


def check_view_spikes(session, lookback_date: date) -> list:
    """Detect view_count_increase spikes >5x the 7-day moving average."""
    rows = session.execute(text("""
        WITH recent AS (
            SELECT ad_id, metric_date, view_count_increase,
                   AVG(view_count_increase) OVER (
                       PARTITION BY ad_id
                       ORDER BY metric_date
                       ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING
                   ) as avg_7d
            FROM ad_daily_metrics
            WHERE metric_date >= :lookback
        )
        SELECT ad_id, metric_date, view_count_increase, ROUND(avg_7d::numeric, 0) as avg_7d
        FROM recent
        WHERE avg_7d > 0
          AND view_count_increase > avg_7d * :multiplier
        ORDER BY view_count_increase DESC
        LIMIT 20
    """), {"lookback": lookback_date, "multiplier": SPIKE_MULTIPLIER}).fetchall()

    return [{
        "ad_id": r[0], "date": str(r[1]),
        "view_increase": r[2], "avg_7d": int(r[3]),
        "ratio": round(r[2] / r[3], 1) if r[3] else 0,
    } for r in rows]


def check_sudden_drops(session, lookback_date: date) -> list:
    """Detect ads that had >1000 view_increase then dropped to 0."""
    rows = session.execute(text("""
        SELECT m.ad_id, m.metric_date, m.view_count_increase,
               prev.view_count_increase as prev_increase, prev.metric_date as prev_date
        FROM ad_daily_metrics m
        JOIN ad_daily_metrics prev ON m.ad_id = prev.ad_id
            AND prev.metric_date = m.metric_date - INTERVAL '1 day'
        WHERE m.metric_date >= :lookback
          AND m.view_count_increase = 0
          AND prev.view_count_increase > 1000
        ORDER BY prev.view_count_increase DESC
        LIMIT 20
    """), {"lookback": lookback_date}).fetchall()

    return [{
        "ad_id": r[0], "date": str(r[1]),
        "current_increase": r[2], "previous_increase": r[3],
    } for r in rows]


def check_negative_values(session, lookback_date: date) -> list:
    """Detect negative view counts or spend."""
    rows = session.execute(text("""
        SELECT ad_id, metric_date, view_count, view_count_increase,
               estimated_spend, estimated_spend_increase
        FROM ad_daily_metrics
        WHERE metric_date >= :lookback
          AND (view_count < 0 OR view_count_increase < 0
               OR estimated_spend < 0 OR estimated_spend_increase < 0)
        ORDER BY metric_date DESC
        LIMIT 20
    """), {"lookback": lookback_date}).fetchall()

    return [{
        "ad_id": r[0], "date": str(r[1]),
        "view_count": r[2], "view_increase": r[3],
        "spend": float(r[4]), "spend_increase": float(r[5]),
    } for r in rows]


def check_spend_outliers(session, lookback_date: date) -> list:
    """Detect spend values >3 standard deviations from the platform mean."""
    rows = session.execute(text("""
        WITH platform_stats AS (
            SELECT platform,
                   AVG(estimated_spend_increase) as avg_spend,
                   STDDEV(estimated_spend_increase) as std_spend
            FROM ad_daily_metrics
            WHERE metric_date >= :lookback
              AND estimated_spend_increase > 0
            GROUP BY platform
        )
        SELECT m.ad_id, m.metric_date, m.platform,
               m.estimated_spend_increase,
               ROUND(ps.avg_spend::numeric, 0) as platform_avg,
               ROUND(ps.std_spend::numeric, 0) as platform_std
        FROM ad_daily_metrics m
        JOIN platform_stats ps ON m.platform = ps.platform
        WHERE m.metric_date >= :lookback
          AND ps.std_spend > 0
          AND m.estimated_spend_increase > ps.avg_spend + 3 * ps.std_spend
        ORDER BY m.estimated_spend_increase DESC
        LIMIT 20
    """), {"lookback": lookback_date}).fetchall()

    return [{
        "ad_id": r[0], "date": str(r[1]), "platform": r[2],
        "spend_increase": float(r[3]),
        "platform_avg": int(r[4]), "platform_std": int(r[5]),
    } for r in rows]


def check_stale_ads(session, stale_days: int = STALE_THRESHOLD_DAYS) -> list:
    """Detect active ads with no recent metrics."""
    rows = session.execute(text("""
        SELECT a.id, a.advertiser_name, a.platform,
               MAX(m.metric_date) as last_metric_date,
               (CURRENT_DATE - MAX(m.metric_date)) as days_since
        FROM ads a
        LEFT JOIN ad_daily_metrics m ON a.id = m.ad_id
        WHERE a.status != 'inactive'
        GROUP BY a.id, a.advertiser_name, a.platform
        HAVING MAX(m.metric_date) IS NULL
           OR (CURRENT_DATE - MAX(m.metric_date)) > :stale_days
        ORDER BY MAX(m.metric_date) NULLS FIRST
        LIMIT 20
    """), {"stale_days": stale_days}).fetchall()

    return [{
        "ad_id": r[0], "advertiser": r[1], "platform": str(r[2]),
        "last_metric_date": str(r[3]) if r[3] else "never",
        "days_since": r[4] if r[4] else None,
    } for r in rows]


def main():
    parser = argparse.ArgumentParser(description="Detect metric anomalies")
    parser.add_argument("--days", type=int, default=DEFAULT_LOOKBACK_DAYS,
                        help=f"Lookback period in days (default: {DEFAULT_LOOKBACK_DAYS})")
    parser.add_argument("--json-report", type=str, help="Export report to JSON")
    args = parser.parse_args()

    lookback_date = date.today() - timedelta(days=args.days)

    print("=" * 60)
    print("  Metric Anomaly Detection")
    print(f"  Lookback: {args.days} days (since {lookback_date})")
    print("=" * 60)

    session = SyncSessionLocal()
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "lookback_days": args.days,
        "anomalies": {},
        "total_anomalies": 0,
    }

    try:
        checks = [
            ("view_spikes", "View count spikes (>5x avg)", check_view_spikes, (session, lookback_date)),
            ("sudden_drops", "Sudden drops to zero", check_sudden_drops, (session, lookback_date)),
            ("negative_values", "Negative values", check_negative_values, (session, lookback_date)),
            ("spend_outliers", "Spend outliers (>3σ)", check_spend_outliers, (session, lookback_date)),
            ("stale_ads", "Stale ads (no recent metrics)", check_stale_ads, (session,)),
        ]

        for key, label, fn, fn_args in checks:
            try:
                results = fn(*fn_args)
            except Exception as e:
                results = []
                print(f"\n  [--] {label}: skipped ({e})")
                continue

            report["anomalies"][key] = results
            report["total_anomalies"] += len(results)

            icon = "!!" if results else "OK"
            print(f"\n  [{icon}] {label}: {len(results)} found")
            for item in results[:3]:
                print(f"      > ad_id={item['ad_id']} {item.get('date', '')}")

        # Summary
        print(f"\n  Total anomalies: {report['total_anomalies']}")
        if report["total_anomalies"] == 0:
            print("  Status: CLEAN")
        else:
            print("  Status: REVIEW NEEDED")

        if args.json_report:
            os.makedirs(os.path.dirname(args.json_report) or ".", exist_ok=True)
            with open(args.json_report, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
            print(f"\n  Exported: {args.json_report}")

        print()
    except Exception as e:
        print(f"\n  ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
