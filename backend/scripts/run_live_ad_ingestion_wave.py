#!/usr/bin/env python3
"""Run a priority live-ingestion crawl wave.

Targets stale keywords first, then queues recent incomplete ads for backfill.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/run_live_ad_ingestion_wave.py --keyword-limit 8 --limit-per-platform 20
    python scripts/run_live_ad_ingestion_wave.py --dry-run
"""

import argparse
import io
import json
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

if __name__ == "__main__" and getattr(sys.stdout, "buffer", None) is not None:
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

from app.tasks.crawl_tasks import (
    get_live_ingestion_policy,
    get_meta_token_runtime_health,
    crawl_ads_task,
    get_connected_platforms,
    get_today_keywords,
    is_duplicate_crawl,
    run_live_ingestion_wave_task,
    _collect_recent_query_stats,
)
from app.services.data_quality_report import build_meta_completion_audit


def _get_session():
    """Get DB session with SQLite fallback for local ops scripts."""
    try:
        from app.core.database import SyncSessionLocal
        session = SyncSessionLocal()
        session.execute(__import__("sqlalchemy").text("SELECT 1"))
        return session
    except Exception:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        db_path = os.path.join(BASE_DIR, "vaap_local.db")
        engine = create_engine(f"sqlite:///{db_path}")
        Session = sessionmaker(bind=engine)
        return Session()


def _patch_local_task_sessions():
    """Force crawl_tasks to use local SQLite when primary DB is unavailable."""
    try:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker
        from app.tasks import crawl_tasks as crawl_tasks_module

        db_path = os.path.join(BASE_DIR, "vaap_local.db")
        if not os.path.exists(db_path):
            return
        engine = create_engine(f"sqlite:///{db_path}")
        LocalSession = sessionmaker(bind=engine)
        crawl_tasks_module.SyncSessionLocal = LocalSession
        import app.core.database as db_module
        db_module.SyncSessionLocal = LocalSession
    except Exception:
        pass


def _run_crawl_inline(keyword: str, platforms: list[str], limit_per_platform: int, country: str):
    """Run crawl task synchronously when no worker is consuming the queue."""
    runner = getattr(crawl_ads_task, "run", crawl_ads_task)
    if getattr(crawl_ads_task, "run", None):
        return runner(
            query=keyword,
            platforms=platforms,
            limit_per_platform=limit_per_platform,
            country=country,
        )
    inline_job_id = f"inline-{keyword}-{uuid.uuid4().hex[:8]}"
    dummy = SimpleNamespace(request=SimpleNamespace(id=inline_job_id, retries=0), max_retries=2, retry=lambda exc=None: (_ for _ in ()).throw(exc or RuntimeError("retry")))
    return runner(
        dummy,
        query=keyword,
        platforms=platforms,
        limit_per_platform=limit_per_platform,
        country=country,
    )


def _cleanup_stale_inline_jobs(session, *, stale_after_minutes: int = 30) -> int:
    """Mark abandoned inline ingestion jobs as failed."""
    from app.models.crawl_job import CrawlFailureReason, CrawlJob, CrawlJobStatusEnum

    cutoff = datetime.now(timezone.utc) - timedelta(minutes=max(1, stale_after_minutes))
    stale_jobs = (
        session.query(CrawlJob)
        .filter(
            CrawlJob.status == CrawlJobStatusEnum.RUNNING,
            CrawlJob.job_id.like("inline-%"),
            CrawlJob.updated_at < cutoff,
        )
        .all()
    )
    if not stale_jobs:
        return 0

    cleaned = 0
    for job in stale_jobs:
        job.status = CrawlJobStatusEnum.FAILED
        job.failure_reason = CrawlFailureReason.TIMEOUT.value
        job.error_message = "stale inline ingestion job cleaned up by scheduler"
        cleaned += 1

    session.commit()
    return cleaned


def _summarize_wave_result(result: dict) -> dict:
    summary = {
        "new_saves": 0,
        "merged_updates": 0,
        "backfilled_creatives": 0,
        "backfilled_lps": 0,
        "queued_backfill_ads": 0,
        "queued_keywords": len(result.get("queued_keywords") or []),
        "skipped_keywords": len(result.get("skipped_keywords") or []),
    }
    for item in result.get("results") or []:
        if not isinstance(item, dict):
            continue
        summary["new_saves"] += int(item.get("saved_count", 0) or 0)
        summary["merged_updates"] += int(item.get("merged_count", 0) or 0)
        summary["backfilled_creatives"] += int(item.get("creative_backfill_count", 0) or 0)
        summary["backfilled_lps"] += int(item.get("lp_backfill_count", 0) or 0)
    backfill = result.get("backfill") or {}
    summary["queued_backfill_ads"] = int(backfill.get("queued", 0) or 0)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description="Run live ad ingestion wave")
    parser.add_argument("--keyword-limit", type=int, default=8)
    parser.add_argument("--limit-per-platform", type=int, default=20)
    parser.add_argument("--country", type=str, default="JP")
    parser.add_argument("--mode", type=str, default="hourly", choices=["hourly", "nightly"])
    parser.add_argument("--inline", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--meta-only", action="store_true")
    args = parser.parse_args()

    _patch_local_task_sessions()
    session = _get_session()
    try:
        cleaned_stale_jobs = _cleanup_stale_inline_jobs(session)
        active_platforms = get_connected_platforms()
        if args.meta_only:
            active_platforms = [platform for platform in active_platforms if platform in {"facebook", "instagram"}]
        policy = get_live_ingestion_policy(active_platforms, mode=args.mode)
        token_health = get_meta_token_runtime_health(session) if active_platforms and all(platform in {"facebook", "instagram"} for platform in active_platforms) else {
            "checked": False,
            "status": "not_applicable",
            "token_source": "missing",
            "recent_auth_failures": 0,
            "latest_auth_failure_at": None,
            "warning": None,
            "fallback_policy": "not_applicable",
        }
        keywords = get_today_keywords(
            prioritize_stale=True,
            session=session,
            limit=args.keyword_limit,
            dynamic_quota=policy.get("dynamic_quota"),
        )
        recent_stats = _collect_recent_query_stats(session, hours=72)

        if args.dry_run:
            payload = {
                "platforms": active_platforms,
                "mode": args.mode,
                "meta_only": args.meta_only,
                "policy": policy,
                "meta_token": token_health,
                "keywords": keywords,
                "duplicate_guard": {
                    keyword: is_duplicate_crawl(session, keyword, hours=policy["duplicate_guard_hours"])
                    for keyword in keywords
                },
                "recent_query_stats": recent_stats,
            }
            print(json.dumps(payload, ensure_ascii=False, indent=2))
            return

        if args.inline:
            inline_results = []
            for keyword in keywords:
                if is_duplicate_crawl(session, keyword, hours=policy["duplicate_guard_hours"]):
                    continue
                inline_results.append(
                    _run_crawl_inline(
                        keyword=keyword,
                        platforms=active_platforms,
                        limit_per_platform=args.limit_per_platform,
                        country=args.country,
                    )
                )
            result = {
                "status": "completed_inline",
                "platforms": active_platforms,
                "mode": args.mode,
                "meta_only": args.meta_only,
                "policy": policy,
                "meta_token": token_health,
                "keywords": keywords,
                "results": inline_results,
            }
        else:
            task_runner = getattr(run_live_ingestion_wave_task, "run", run_live_ingestion_wave_task)
            if getattr(run_live_ingestion_wave_task, "run", None):
                result = task_runner(
                    platforms=active_platforms,
                    keyword_limit=args.keyword_limit,
                    limit_per_platform=args.limit_per_platform,
                    country=args.country,
                    queue_backfill=True,
                    mode=args.mode,
                )
            else:
                result = task_runner(
                    None,
                    platforms=active_platforms,
                    keyword_limit=args.keyword_limit,
                    limit_per_platform=args.limit_per_platform,
                    country=args.country,
                    queue_backfill=True,
                    mode=args.mode,
                )

        result["mode"] = args.mode
        result["meta_only"] = args.meta_only
        result["policy"] = result.get("policy") or policy
        result["meta_token"] = result.get("meta_token") or token_health
        result["operations_summary"] = _summarize_wave_result(result)
        result["cleaned_stale_inline_jobs"] = cleaned_stale_jobs

        result["meta_completion_audit"] = build_meta_completion_audit(session, top_n=5)["summary"]

        # Print a compact operations summary for cron / scheduler logs.
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))
    finally:
        try:
            session.close()
        except Exception:
            pass


if __name__ == "__main__":
    main()
