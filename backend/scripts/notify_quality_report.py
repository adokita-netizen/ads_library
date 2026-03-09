"""A85 (CI-115): Data quality report Slack notification.

Runs a quick data quality check and sends a summary to Slack via webhook.
Designed for daily cron execution.

Requires SLACK_WEBHOOK_URL environment variable.

Usage:
    python -m scripts.notify_quality_report
    python -m scripts.notify_quality_report --dry-run  # print without sending
"""

import argparse
import json
import os
import sys
import urllib.request
import urllib.error
from datetime import date, datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.core.database import SyncSessionLocal


def collect_quality_summary(session) -> dict:
    """Collect quality metrics for the daily report."""
    summary = {}

    # Total ads
    summary["total_ads"] = session.execute(text("SELECT COUNT(*) FROM ads")).scalar()

    # Today's metrics
    summary["metrics_today"] = session.execute(text(
        "SELECT COUNT(*) FROM ad_daily_metrics WHERE metric_date = CURRENT_DATE"
    )).scalar()

    # Yesterday's metrics (for comparison)
    summary["metrics_yesterday"] = session.execute(text(
        "SELECT COUNT(*) FROM ad_daily_metrics WHERE metric_date = CURRENT_DATE - 1"
    )).scalar()

    # Orphaned metrics
    summary["orphaned_metrics"] = session.execute(text("""
        SELECT COUNT(*) FROM ad_daily_metrics m
        LEFT JOIN ads a ON m.ad_id = a.id WHERE a.id IS NULL
    """)).scalar()

    # Ads missing scores
    summary["ads_no_score"] = session.execute(text("""
        SELECT COUNT(*) FROM ads WHERE ad_metadata->>'latest_hit_score' IS NULL
    """)).scalar()

    # Ads missing creative analysis
    summary["ads_no_creative"] = session.execute(text("""
        SELECT COUNT(*) FROM ads WHERE ad_metadata->>'creative_analysis' IS NULL
    """)).scalar()

    # Negative values
    summary["negative_values"] = session.execute(text("""
        SELECT COUNT(*) FROM ad_daily_metrics
        WHERE view_count < 0 OR estimated_spend < 0
    """)).scalar()

    # Grade
    issues = summary["orphaned_metrics"] + summary["negative_values"]
    if issues == 0:
        summary["grade"] = "A"
    elif issues <= 5:
        summary["grade"] = "B"
    elif issues <= 20:
        summary["grade"] = "C"
    else:
        summary["grade"] = "D"

    return summary


def format_slack_message(summary: dict) -> dict:
    """Format the quality report as a Slack message payload."""
    grade_emoji = {"A": ":white_check_mark:", "B": ":large_blue_circle:", "C": ":warning:", "D": ":red_circle:"}.get(
        summary["grade"], ":question:"
    )
    today = date.today().isoformat()

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"Data Quality Report — {today}"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"{grade_emoji} *Grade: {summary['grade']}*"
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Total Ads:* {summary['total_ads']}"},
                {"type": "mrkdwn", "text": f"*Metrics Today:* {summary['metrics_today']}"},
                {"type": "mrkdwn", "text": f"*Metrics Yesterday:* {summary['metrics_yesterday']}"},
                {"type": "mrkdwn", "text": f"*Orphaned Metrics:* {summary['orphaned_metrics']}"},
                {"type": "mrkdwn", "text": f"*No Score:* {summary['ads_no_score']}"},
                {"type": "mrkdwn", "text": f"*No Creative:* {summary['ads_no_creative']}"},
                {"type": "mrkdwn", "text": f"*Negative Values:* {summary['negative_values']}"},
            ]
        },
    ]

    # Alert if metrics dropped
    if summary["metrics_yesterday"] > 0 and summary["metrics_today"] == 0:
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": ":rotating_light: *No metrics collected today!* Check daily job."
            }
        })

    return {"blocks": blocks}


def send_slack(webhook_url: str, payload: dict) -> bool:
    """Send a message to Slack via webhook. Returns True on success."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.URLError as e:
        print(f"  Slack send failed: {e}")
        return False


def main():
    parser = argparse.ArgumentParser(description="Send data quality report to Slack")
    parser.add_argument("--dry-run", action="store_true", help="Print report without sending")
    args = parser.parse_args()

    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")

    print("=" * 60)
    print("  Data Quality Report → Slack")
    print("=" * 60)

    session = SyncSessionLocal()
    try:
        summary = collect_quality_summary(session)

        print(f"\n  Grade: {summary['grade']}")
        print(f"  Total ads: {summary['total_ads']}")
        print(f"  Metrics today: {summary['metrics_today']}")
        print(f"  Orphaned: {summary['orphaned_metrics']}")
        print(f"  Negative values: {summary['negative_values']}")

        payload = format_slack_message(summary)

        if args.dry_run:
            print("\n  DRY-RUN: Slack payload:")
            print(json.dumps(payload, indent=2, ensure_ascii=False))
            return

        if not webhook_url:
            print("\n  SLACK_WEBHOOK_URL not set. Set it to enable notifications.")
            print("  Run with --dry-run to see the report format.")
            return

        print("\n  Sending to Slack...")
        if send_slack(webhook_url, payload):
            print("  Sent successfully!")
        else:
            print("  Failed to send.")

    except Exception as e:
        print(f"\n  ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
