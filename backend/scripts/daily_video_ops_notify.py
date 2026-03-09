"""Run daily video ops and send webhook alert on failures/warnings.

Env vars:
  DAILY_VIDEO_OPS_WEBHOOK_URL (fallback: SLACK_WEBHOOK_URL)
  DAILY_VIDEO_OPS_NOTIFY_SUCCESS=1 to send success notifications too
"""

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.tasks.video_tasks import daily_video_ops_task


def _send_webhook(webhook_url: str, payload: dict) -> bool:
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        webhook_url,
        data=data,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except urllib.error.URLError:
        return False


def _build_payload(level: str, result: dict) -> dict:
    report = result.get("report_video_analysis", {})
    analyze = result.get("analyze_new_videos", {})
    text = (
        f"[daily_video_ops] {level}\n"
        f"coverage={report.get('analysis_coverage_pct')}% "
        f"analyzed={report.get('video_analyzed_true')}/{report.get('total_video_ads')} "
        f"skipped={report.get('video_skipped_count')} "
        f"new_target={analyze.get('target_count')} ok={analyze.get('ok')} failed={analyze.get('failed')}"
    )
    return {
        "text": text,
        "meta": {
            "level": level,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "result": result,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run daily video ops with webhook alerts")
    parser.add_argument("--analyze-limit", type=int, default=50)
    parser.add_argument("--sample-limit", type=int, default=10)
    parser.add_argument("--webhook-url", type=str, default="", help="Override webhook URL for this run.")
    parser.add_argument(
        "--force-level",
        choices=["OK", "WARN", "ERROR"],
        default="",
        help="Force notification level for connectivity testing.",
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    result = daily_video_ops_task(analyze_limit=args.analyze_limit, sample_limit=args.sample_limit)
    report = result.get("report_video_analysis", {})
    analyze = result.get("analyze_new_videos", {})

    coverage = float(report.get("analysis_coverage_pct", 0.0))
    skipped = int(report.get("video_skipped_count", 0))
    failed = int(analyze.get("failed", 0))

    level = "OK"
    exit_code = 0
    if failed > 0:
        level = "ERROR"
        exit_code = 2
    elif skipped > 0 or coverage < 100.0:
        level = "WARN"
        exit_code = 1

    if args.force_level:
        level = args.force_level
        exit_code = 0 if level == "OK" else (1 if level == "WARN" else 2)

    print(json.dumps({"level": level, "result": result}, ensure_ascii=False))

    webhook_url = args.webhook_url or os.getenv("DAILY_VIDEO_OPS_WEBHOOK_URL") or os.getenv("SLACK_WEBHOOK_URL", "")
    notify_success = os.getenv("DAILY_VIDEO_OPS_NOTIFY_SUCCESS", "0") == "1"
    should_notify = level != "OK" or notify_success

    if args.dry_run:
        print(json.dumps({"notify": should_notify, "webhook_configured": bool(webhook_url)}, ensure_ascii=False))
        return exit_code

    if should_notify and webhook_url:
        payload = _build_payload(level, result)
        sent = _send_webhook(webhook_url, payload)
        print(json.dumps({"notify_sent": sent, "level": level}, ensure_ascii=False))
    else:
        print(json.dumps({"notify_skipped": True, "reason": "no_webhook_or_ok_level"}, ensure_ascii=False))

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
