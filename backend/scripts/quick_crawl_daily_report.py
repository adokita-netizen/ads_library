"""A-BRW-2: Daily quick-crawl success/failure analytics.

Aggregates quick-crawl jobs by day and failure reason.

Usage:
    python -m scripts.quick_crawl_daily_report
    python -m scripts.quick_crawl_daily_report --days 14 --json-report exports/quick_crawl_daily_report.json
"""

import argparse
import json
import os
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from app.core.database import SyncSessionLocal
from app.models.crawl_job import CrawlJob


def _classify_error_message(error_msg: str | None) -> str:
    text = str(error_msg or "").lower()
    if "timeout" in text:
        return "timeout"
    if "429" in text or "rate" in text:
        return "rate_limit"
    if "401" in text or "token" in text or "auth" in text:
        return "auth_expired"
    if "parse" in text or "json" in text or "decode" in text:
        return "parse_error"
    if "connect" in text or "network" in text or "dns" in text:
        return "network_error"
    if "browser" in text or "chromium" in text or "playwright" in text:
        return "browser_crash"
    return "unknown"


def _classify_zero_save_cause(progress_detail: dict | None) -> str:
    detail = progress_detail if isinstance(progress_detail, dict) else {}
    fetched = int(detail.get("fetched_ads_count") or 0)
    saved = int(detail.get("saved_ads_count") or 0)
    inserted = int(detail.get("inserted_count") or 0)
    updated = int(detail.get("updated_count") or 0)
    skipped_invalid = int(detail.get("skipped_invalid_count") or 0)
    dropped = int(detail.get("dropped_after_filter_count") or 0)
    if saved > 0:
        return "saved"
    if fetched == 0:
        return "no_fetch_results"
    if skipped_invalid >= fetched and fetched > 0:
        return "invalid_payload_only"
    if dropped >= fetched and fetched > 0:
        return "filtered_out"
    if inserted == 0 and updated == 0 and fetched > 0:
        return "unmatched_or_unpersisted"
    return "unknown"


def main():
    parser = argparse.ArgumentParser(description="Generate quick-crawl daily success/failure report")
    parser.add_argument("--days", type=int, default=7, help="Lookback window in days")
    parser.add_argument(
        "--min-success-rate",
        type=float,
        default=None,
        help="If set, exit 1 when overall success_rate is below this threshold (0-1)",
    )
    parser.add_argument(
        "--top-failing-queries",
        type=int,
        default=10,
        help="Number of top failing queries to include in report",
    )
    parser.add_argument(
        "--json-report",
        type=str,
        default="exports/quick_crawl_daily_report.json",
        help="JSON output path",
    )
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, args.days))
    session = SyncSessionLocal()
    try:
        jobs = (
            session.query(CrawlJob)
            .filter(CrawlJob.created_at >= cutoff)
            .filter(CrawlJob.query.isnot(None))
            .order_by(CrawlJob.created_at.asc())
            .all()
        )

        daily = defaultdict(
            lambda: {
                "total": 0,
                "completed": 0,
                "failed": 0,
                "success_rate": 0.0,
                "failure_reasons": defaultdict(int),
            }
        )
        totals = {
            "total_jobs": 0,
            "completed": 0,
            "failed": 0,
            "failure_reasons": defaultdict(int),
            "zero_save_completed": 0,
            "zero_save_causes": defaultdict(int),
        }
        failing_queries = defaultdict(lambda: {"failed": 0, "total": 0, "reasons": defaultdict(int)})
        platform_stats = defaultdict(lambda: {"total": 0, "completed": 0, "failed": 0, "zero_save_completed": 0})

        for job in jobs:
            day = (job.created_at or datetime.now(timezone.utc)).date().isoformat()
            reason = (job.failure_reason or "").strip() or _classify_error_message(job.error_message)
            status = (job.status.value if hasattr(job.status, "value") else str(job.status)).lower()
            detail = job.progress_detail if isinstance(job.progress_detail, dict) else {}
            saved = int(detail.get("saved_ads_count") or 0)
            zero_save_cause = _classify_zero_save_cause(detail)
            platforms = job.platforms if isinstance(job.platforms, list) else []
            norm_platforms = [str(p).strip().lower() for p in platforms if str(p).strip()] or ["unknown"]

            daily[day]["total"] += 1
            totals["total_jobs"] += 1

            if status == "completed":
                daily[day]["completed"] += 1
                totals["completed"] += 1
                if saved == 0:
                    totals["zero_save_completed"] += 1
                    totals["zero_save_causes"][zero_save_cause] += 1
            elif status == "failed":
                daily[day]["failed"] += 1
                daily[day]["failure_reasons"][reason] += 1
                totals["failed"] += 1
                totals["failure_reasons"][reason] += 1
                q = (job.query or "").strip()
                if q:
                    failing_queries[q]["failed"] += 1
                    failing_queries[q]["reasons"][reason] += 1

            q = (job.query or "").strip()
            if q:
                failing_queries[q]["total"] += 1

            for p in norm_platforms:
                platform_stats[p]["total"] += 1
                if status == "completed":
                    platform_stats[p]["completed"] += 1
                    if saved == 0:
                        platform_stats[p]["zero_save_completed"] += 1
                elif status == "failed":
                    platform_stats[p]["failed"] += 1

        for day, row in daily.items():
            if row["total"] > 0:
                row["success_rate"] = round(row["completed"] / row["total"], 4)
            row["failure_reasons"] = dict(sorted(row["failure_reasons"].items(), key=lambda x: -x[1]))

        top_failing_queries = sorted(
            [
                {
                    "query": q,
                    "failed": v["failed"],
                    "total": v["total"],
                    "failure_rate": round((v["failed"] / v["total"]), 4) if v["total"] else 0.0,
                    "top_reasons": dict(sorted(v["reasons"].items(), key=lambda x: -x[1])[:3]),
                }
                for q, v in failing_queries.items()
                if v["failed"] > 0
            ],
            key=lambda row: (row["failed"], row["failure_rate"]),
            reverse=True,
        )[: max(1, args.top_failing_queries)]

        overall_success_rate = (
            round((totals["completed"] / totals["total_jobs"]), 4) if totals["total_jobs"] else 0.0
        )
        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_days": args.days,
            "summary": {
                "total_jobs": totals["total_jobs"],
                "completed": totals["completed"],
                "failed": totals["failed"],
                "success_rate": overall_success_rate,
                "failure_reasons": dict(sorted(totals["failure_reasons"].items(), key=lambda x: -x[1])),
                "zero_save_completed": totals["zero_save_completed"],
                "zero_save_rate_among_completed": round(
                    (totals["zero_save_completed"] / totals["completed"]), 4
                ) if totals["completed"] else 0.0,
                "zero_save_causes": dict(sorted(totals["zero_save_causes"].items(), key=lambda x: -x[1])),
            },
            "daily": {k: daily[k] for k in sorted(daily.keys())},
            "top_failing_queries": top_failing_queries,
            "platforms": sorted(
                [
                    {
                        "platform": p,
                        "total": s["total"],
                        "completed": s["completed"],
                        "failed": s["failed"],
                        "zero_save_completed": s["zero_save_completed"],
                        "failure_rate": round((s["failed"] / s["total"]), 4) if s["total"] else 0.0,
                        "zero_save_rate": round((s["zero_save_completed"] / s["completed"]), 4) if s["completed"] else 0.0,
                    }
                    for p, s in platform_stats.items()
                ],
                key=lambda row: (row["zero_save_completed"], row["failed"], row["total"]),
                reverse=True,
            ),
        }

        out_dir = os.path.dirname(args.json_report) or "."
        os.makedirs(out_dir, exist_ok=True)
        with open(args.json_report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"Jobs analyzed: {len(jobs)}")
        print(f"Window days:   {args.days}")
        print(f"Success rate:  {report['summary']['success_rate']:.2%}")
        print(f"Report:        {args.json_report}")

        if args.min_success_rate is not None and overall_success_rate < args.min_success_rate:
            print(
                f"ALERT: success_rate {overall_success_rate:.2%} is below threshold {args.min_success_rate:.2%}"
            )
            raise SystemExit(1)

    finally:
        session.close()


if __name__ == "__main__":
    main()
