"""A39: audit crawl job insert/search consistency from stored progress_detail."""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta, timezone

from app.core.database import SyncSessionLocal
from app.models.crawl_job import CrawlJob


def build_crawl_search_consistency_audit(session, *, days: int = 7, top_n: int = 20) -> dict:
    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, days))
    jobs = (
        session.query(CrawlJob)
        .filter(CrawlJob.created_at >= cutoff)
        .order_by(CrawlJob.created_at.desc())
        .all()
    )

    rows = []
    root_causes = Counter()
    for job in jobs:
        detail = job.progress_detail if isinstance(job.progress_detail, dict) else {}
        inserted = int(detail.get("inserted_count") or detail.get("new_ads_count") or 0)
        searchable = int(detail.get("searchable_ads_count") or inserted)
        delta = max(0, inserted - searchable)
        status = str(getattr(job.status, "value", job.status)).lower()
        failure_reason = str(job.failure_reason or "").strip().lower()
        is_consistent = delta <= 2 and status != "failed"
        if status == "failed":
            root_cause = f"failed:{failure_reason or 'unknown'}"
        elif not is_consistent:
            root_cause = "search_reflection_gap"
        else:
            root_cause = "consistent"
        root_causes[root_cause] += 1
        rows.append(
            {
                "job_id": job.job_id,
                "query": job.query,
                "status": status,
                "inserted_count": inserted,
                "search_visible_count": searchable,
                "delta": delta,
                "is_consistent": is_consistent,
                "failure_reason": failure_reason or None,
                "root_cause": root_cause,
                "created_at": job.created_at.isoformat() if job.created_at else None,
            }
        )

    inconsistent = [row for row in rows if not row["is_consistent"]]
    inconsistent.sort(key=lambda item: (-item["delta"], item["job_id"]))

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "summary": {
            "jobs_seen": len(rows),
            "inconsistent_jobs": len(inconsistent),
            "consistency_rate": round((len(rows) - len(inconsistent)) / len(rows), 4) if rows else 1.0,
        },
        "root_cause_counts": dict(root_causes),
        "inconsistent_jobs_top_n": inconsistent[: max(1, top_n)],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit crawl -> search consistency using stored crawl jobs")
    parser.add_argument("--days", type=int, default=7)
    parser.add_argument("--top-n", type=int, default=20)
    parser.add_argument("--json-report", type=str)
    args = parser.parse_args()

    session = SyncSessionLocal()
    try:
        report = build_crawl_search_consistency_audit(session, days=args.days, top_n=args.top_n)
    finally:
        session.close()

    summary = report["summary"]
    print(f"jobs_seen:          {summary['jobs_seen']}")
    print(f"inconsistent_jobs:  {summary['inconsistent_jobs']}")
    print(f"consistency_rate:   {summary['consistency_rate']:.2%}")

    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(f"report:             {args.json_report}")


if __name__ == "__main__":
    main()
