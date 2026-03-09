"""A40/A41: ads volume health audit + recovery planning.

Reports daily volume health, save failures, incomplete-record rates,
and query/platform low-volume recovery opportunities.
"""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

import requests

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.crawl_job import CrawlJob


def _normalize_query(raw: str | None) -> str:
    return str(raw or "").replace("\u3000", " ").strip()


def _extract_country(progress_detail: dict | None) -> str:
    if not isinstance(progress_detail, dict):
        return "JP"
    value = str(progress_detail.get("country") or "").strip().upper()
    return value or "JP"


def _classify_root_cause(
    runs: int,
    failed: int,
    zero: int,
    low: int,
    failure_reasons: Counter,
) -> str:
    if runs <= 0:
        return "no_data"
    failed_rate = failed / runs
    zero_rate = zero / runs
    low_rate = low / runs
    if failed_rate >= 0.5 and failure_reasons:
        return f"pipeline_failure:{failure_reasons.most_common(1)[0][0]}"
    if zero_rate >= 0.5:
        return "no_results_or_filtering"
    if low_rate >= 0.5:
        return "low_yield_keyword"
    return "stable"


def _build_helper_queries(base_query: str) -> list[str]:
    q = _normalize_query(base_query).lower()
    mapping = {
        "glp-1": [
            "医療ダイエット",
            "メディカルダイエット",
            "GLP-1 クリニック",
            "痩身クリニック",
            "オンライン診療 ダイエット",
        ],
        "医療ダイエット": [
            "GLP-1 ダイエット",
            "痩身クリニック",
            "オンライン診療 ダイエット",
        ],
        "ダイエット": ["医療ダイエット", "脂肪冷却", "痩身", "痩身クリニック"],
        "脱毛": ["医療脱毛", "全身脱毛", "美容クリニック", "vio脱毛", "脱毛サロン"],
        "美容": ["美容クリニック", "美肌", "シミ取り", "アンチエイジング", "美容皮膚科"],
        "健康": ["サプリ", "腸活", "睡眠改善", "血糖値", "ヘルスケア"],
        "投資": ["資産運用", "nisa", "株式投資", "新nisa", "投資信託"],
        "副業": ["在宅ワーク", "フリーランス", "副収入", "sns運用", "スキル販売"],
        "不動産": ["不動産投資", "マンション投資", "住宅ローン", "賃貸経営", "物件比較"],
    }
    for key, values in mapping.items():
        if key in q:
            return values
    return ["美容", "健康", "サプリ"]


def _run_quick_crawl(api_base: str, query: str, limit: int, timeout_sec: int) -> dict:
    endpoint = f"{api_base.rstrip('/')}/rankings/quick-crawl"
    payload = {"query": query, "limit": limit}
    try:
        resp = requests.post(endpoint, json=payload, timeout=timeout_sec)
        body = resp.json() if resp.headers.get("content-type", "").startswith("application/json") else {}
        if resp.status_code != 200:
            return {
                "query": query,
                "ok": False,
                "status_code": resp.status_code,
                "error": body.get("error") or resp.text[:200],
                "fetched_ads_count": 0,
                "new_ads_count": 0,
            }
        return {
            "query": query,
            "ok": True,
            "status_code": 200,
            "fetched_ads_count": int(body.get("fetched_ads_count") or body.get("total_ads_found") or 0),
            "new_ads_count": int(body.get("new_ads_count") or 0),
            "recovery": body.get("recovery"),
        }
    except Exception as exc:
        return {
            "query": query,
            "ok": False,
            "status_code": 0,
            "error": str(exc),
            "fetched_ads_count": 0,
            "new_ads_count": 0,
        }


def _dt(value: object) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    raw = str(value).strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def build_ads_volume_health_report(session, *, days: int, min_ads: int, target_min_ads_per_day: int) -> dict:
    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(days=max(1, days))
    yesterday_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc) - timedelta(days=1)
    today_start = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)
    last_7d_start = today_start - timedelta(days=7)

    jobs = (
        session.query(CrawlJob)
        .filter(CrawlJob.created_at >= cutoff)
        .order_by(CrawlJob.created_at.asc())
        .all()
    )
    ads = session.query(Ad).all()

    daily_new_ads = Counter()
    save_failure_count = 0
    save_failure_reasons = Counter()
    for job in jobs:
        detail = job.progress_detail if isinstance(job.progress_detail, dict) else {}
        created_at = _dt(job.created_at)
        if created_at is None:
            continue
        day_key = created_at.date().isoformat()
        daily_new_ads[day_key] += int(detail.get("new_ads_count") or 0)
        status = str(getattr(job.status, "value", job.status)).lower()
        if status == "failed":
            save_failure_count += 1
            reason = str(job.failure_reason or "unknown").strip().lower() or "unknown"
            save_failure_reasons[reason] += 1

    prev_day_key = yesterday_start.date().isoformat()
    previous_day_ads = daily_new_ads.get(prev_day_key, 0)
    last_7d_values = []
    for day, count in daily_new_ads.items():
        day_dt = _dt(f"{day}T00:00:00+00:00")
        if day_dt and day_dt >= last_7d_start:
            last_7d_values.append(count)
    avg_7d_ads = round(sum(last_7d_values) / len(last_7d_values), 2) if last_7d_values else 0.0

    incomplete_records = []
    field_missing_counts = {
        "title": 0,
        "platform": 0,
        "advertiser_name": 0,
        "destination_url": 0,
    }
    reprocess_pending_count = 0
    for ad in ads:
        meta = ad.ad_metadata if isinstance(ad.ad_metadata, dict) else {}
        reasons = []
        if not str(ad.title or "").strip():
            reasons.append("missing_title")
            field_missing_counts["title"] += 1
        if not getattr(ad, "platform", None):
            reasons.append("missing_platform")
            field_missing_counts["platform"] += 1
        if not str(ad.advertiser_name or "").strip():
            reasons.append("missing_advertiser_name")
            field_missing_counts["advertiser_name"] += 1
        if not str(ad.destination_url or "").strip():
            reasons.append("missing_destination_url")
            field_missing_counts["destination_url"] += 1
        if reasons:
            incomplete_records.append(
                {
                    "ad_id": ad.id,
                    "title": ad.title or "",
                    "reasons": reasons,
                }
            )
        if bool(meta.get("needs_media_retry")) or bool(meta.get("auto_recrawl")) or bool(meta.get("is_incomplete_record")):
            reprocess_pending_count += 1

    total_ads = len(ads)
    field_missing_rates = {
        key: round(value / total_ads, 4) if total_ads else 0.0
        for key, value in field_missing_counts.items()
    }
    return {
        "generated_at": now.isoformat(),
        "window_days": days,
        "target_min_ads_per_day": target_min_ads_per_day,
        "summary": {
            "total_ads": total_ads,
            "previous_day_new_ads": previous_day_ads,
            "seven_day_avg_new_ads": avg_7d_ads,
            "target_met_previous_day": previous_day_ads >= target_min_ads_per_day,
            "save_failure_count": save_failure_count,
            "reprocess_pending_count": reprocess_pending_count,
            "incomplete_record_count": len(incomplete_records),
        },
        "field_missing_counts": field_missing_counts,
        "field_missing_rates": field_missing_rates,
        "save_failure_reasons": dict(save_failure_reasons),
        "incomplete_records_top_n": incomplete_records[:20],
        "warnings": [
            code
            for code, active in (
                ("below_target_min_ads", previous_day_ads < target_min_ads_per_day),
                ("save_failures_present", save_failure_count > 0),
                ("incomplete_records_present", len(incomplete_records) > 0),
                ("reprocess_backlog_present", reprocess_pending_count > 0),
            )
            if active
        ],
    }


def build_daily_recovery_plan(
    *,
    previous_day_new_ads: int,
    target_min_ads_per_day: int,
    focus_keywords: list[str],
    execute_recovery: bool,
    api_base: str,
    recovery_limit: int,
    timeout_sec: int,
) -> dict:
    deficit = max(0, target_min_ads_per_day - previous_day_new_ads)
    should_trigger = deficit > 0
    seed_keywords = focus_keywords or ["GLP-1", "美容", "健康"]
    planned_queries: list[str] = []
    seen: set[str] = set()
    for keyword in seed_keywords:
        candidates = [keyword, *_build_helper_queries(keyword)[:2]]
        for candidate in candidates:
            normalized = _normalize_query(candidate)
            if normalized and normalized.lower() not in seen:
                seen.add(normalized.lower())
                planned_queries.append(normalized)
    planned_queries = planned_queries[: min(6, max(3, deficit // 20 + 1))]

    attempts = []
    total_fetched = 0
    total_new = 0
    if should_trigger and execute_recovery:
        for query in planned_queries:
            result = _run_quick_crawl(
                api_base=api_base,
                query=query,
                limit=recovery_limit,
                timeout_sec=timeout_sec,
            )
            attempts.append(result)
            total_fetched += int(result.get("fetched_ads_count") or 0)
            total_new += int(result.get("new_ads_count") or 0)

    return {
        "should_trigger": should_trigger,
        "deficit": deficit,
        "planned_queries": planned_queries,
        "platform_spread": ["facebook", "instagram"],
        "executed": bool(should_trigger and execute_recovery),
        "attempts": attempts,
        "added_fetched_ads": total_fetched,
        "added_new_ads": total_new,
    }


def main():
    parser = argparse.ArgumentParser(description="Audit crawl volume gaps and run recovery retries")
    parser.add_argument("--days", type=int, default=7, help="Lookback days for audit")
    parser.add_argument("--min-ads", type=int, default=5, help="Threshold for low-volume classification")
    parser.add_argument("--target-min-ads-per-day", type=int, default=100, help="Daily minimum ads target for A40 health audit")
    parser.add_argument(
        "--focus-keywords",
        type=str,
        default="GLP-1",
        help="Comma-separated keywords to inspect deeply (e.g. GLP-1,ダイエット)",
    )
    parser.add_argument("--execute-recovery", action="store_true", help="Run quick-crawl recovery attempts")
    parser.add_argument("--recovery-limit", type=int, default=20, help="Limit per quick-crawl recovery request")
    parser.add_argument("--api-base", type=str, default=os.getenv("VAAP_API_BASE", "http://localhost:8000/api/v1"))
    parser.add_argument("--timeout-sec", type=int, default=180, help="HTTP timeout for recovery calls")
    parser.add_argument(
        "--json-report",
        type=str,
        default=f"exports/ads_volume_audit_{datetime.now(timezone.utc).strftime('%Y%m%d')}.json",
        help="Output JSON report path",
    )
    args = parser.parse_args()

    cutoff = datetime.now(timezone.utc) - timedelta(days=max(1, args.days))
    focus_keywords = [x.strip() for x in args.focus_keywords.split(",") if x.strip()]

    session = SyncSessionLocal()
    try:
        jobs = (
            session.query(CrawlJob)
            .filter(CrawlJob.created_at >= cutoff)
            .filter(CrawlJob.query.isnot(None))
            .order_by(CrawlJob.created_at.asc())
            .all()
        )
        health_report = build_ads_volume_health_report(
            session,
            days=args.days,
            min_ads=args.min_ads,
            target_min_ads_per_day=args.target_min_ads_per_day,
        )

        groups = defaultdict(
            lambda: {
                "runs": 0,
                "failed": 0,
                "zero": 0,
                "low": 0,
                "fetched_ads_sum": 0,
                "new_ads_sum": 0,
                "failure_reasons": Counter(),
            }
        )

        for job in jobs:
            q = _normalize_query(job.query)
            if not q:
                continue
            platforms = job.platforms if isinstance(job.platforms, list) and job.platforms else ["unknown"]
            progress_detail = job.progress_detail if isinstance(job.progress_detail, dict) else {}
            country = _extract_country(progress_detail)
            status = (job.status.value if hasattr(job.status, "value") else str(job.status)).lower()
            fetched_ads_count = int(progress_detail.get("fetched_ads_count") or job.total_ads_found or 0)
            new_ads_count = int(progress_detail.get("new_ads_count") or 0)
            failure_reason = (job.failure_reason or "unknown").strip() or "unknown"

            for platform in platforms:
                key = (q, str(platform), country)
                g = groups[key]
                g["runs"] += 1
                g["fetched_ads_sum"] += fetched_ads_count
                g["new_ads_sum"] += new_ads_count
                if status == "failed":
                    g["failed"] += 1
                    g["failure_reasons"][failure_reason] += 1
                if fetched_ads_count == 0:
                    g["zero"] += 1
                if fetched_ads_count < args.min_ads:
                    g["low"] += 1

        audit_rows = []
        for (query, platform, country), g in groups.items():
            runs = g["runs"]
            avg_fetched = round(g["fetched_ads_sum"] / runs, 2) if runs else 0.0
            avg_new = round(g["new_ads_sum"] / runs, 2) if runs else 0.0
            row = {
                "query": query,
                "platform": platform,
                "country": country,
                "runs": runs,
                "avg_fetched_ads_found": avg_fetched,
                "avg_new_ads_found": avg_new,
                "failed_runs": g["failed"],
                "zero_runs": g["zero"],
                "low_runs": g["low"],
                "failure_reasons": dict(g["failure_reasons"].most_common()),
                "root_cause": _classify_root_cause(
                    runs=runs,
                    failed=g["failed"],
                    zero=g["zero"],
                    low=g["low"],
                    failure_reasons=g["failure_reasons"],
                ),
            }
            audit_rows.append(row)

        audit_rows.sort(key=lambda r: (r["avg_fetched_ads_found"], -r["runs"]))

        focus_analysis = []
        for keyword in focus_keywords:
            keyword_rows = [r for r in audit_rows if keyword.lower() in r["query"].lower()]
            helper_queries = _build_helper_queries(keyword)
            attempts = []
            added_fetched = 0
            added = 0
            if not keyword_rows:
                if args.execute_recovery:
                    for q in [keyword, *helper_queries[:2]]:
                        result = _run_quick_crawl(
                            api_base=args.api_base,
                            query=q,
                            limit=args.recovery_limit,
                            timeout_sec=args.timeout_sec,
                        )
                        attempts.append(result)
                        added_fetched += int(result.get("fetched_ads_count") or 0)
                        added += int(result.get("new_ads_count") or 0)
                focus_analysis.append(
                    {
                        "keyword": keyword,
                        "matched_rows": 0,
                        "before_avg_fetched_ads": 0.0,
                        "before_avg_new_ads": 0.0,
                        "dominant_root_cause": "no_data",
                        "recovery_plan": {
                            "helper_queries": helper_queries,
                            "platform_spread": ["facebook", "instagram"],
                        },
                        "after_fetched_ads": added_fetched,
                        "after_new_ads": added,
                        "recovery_attempts": attempts,
                    }
                )
                continue

            before_fetched_avg = round(sum(r["avg_fetched_ads_found"] for r in keyword_rows) / len(keyword_rows), 2)
            before_new_avg = round(sum(r["avg_new_ads_found"] for r in keyword_rows) / len(keyword_rows), 2)
            dominant_root = Counter(r["root_cause"] for r in keyword_rows).most_common(1)[0][0]
            if args.execute_recovery:
                for q in [keyword, *helper_queries[:2]]:
                    result = _run_quick_crawl(
                        api_base=args.api_base,
                        query=q,
                        limit=args.recovery_limit,
                        timeout_sec=args.timeout_sec,
                    )
                    attempts.append(result)
                    added_fetched += int(result.get("fetched_ads_count") or 0)
                    added += int(result.get("new_ads_count") or 0)

            focus_analysis.append(
                {
                    "keyword": keyword,
                    "matched_rows": len(keyword_rows),
                    "before_avg_fetched_ads": before_fetched_avg,
                    "before_avg_new_ads": before_new_avg,
                    "dominant_root_cause": dominant_root,
                    "recovery_plan": {
                        "helper_queries": helper_queries,
                        "platform_spread": ["facebook", "instagram"],
                    },
                    "after_fetched_ads": added_fetched,
                    "after_new_ads": added,
                    "recovery_attempts": attempts,
                }
            )

        daily_recovery_plan = build_daily_recovery_plan(
            previous_day_new_ads=health_report["summary"]["previous_day_new_ads"],
            target_min_ads_per_day=args.target_min_ads_per_day,
            focus_keywords=focus_keywords,
            execute_recovery=args.execute_recovery,
            api_base=args.api_base,
            recovery_limit=args.recovery_limit,
            timeout_sec=args.timeout_sec,
        )

        report = {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "window_days": args.days,
            "min_ads_threshold": args.min_ads,
            "target_min_ads_per_day": args.target_min_ads_per_day,
            "focus_keywords": focus_keywords,
            "summary": {
                "total_jobs": len(jobs),
                "total_groups": len(audit_rows),
                "zero_or_low_groups": sum(1 for r in audit_rows if r["avg_fetched_ads_found"] < args.min_ads),
            },
            "health": health_report,
            "daily_recovery_plan": daily_recovery_plan,
            "audit_by_query_platform_country": audit_rows,
            "focus_analysis_before_after": focus_analysis,
        }

        out_dir = os.path.dirname(args.json_report) or "."
        os.makedirs(out_dir, exist_ok=True)
        with open(args.json_report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)

        print(f"Jobs analyzed: {len(jobs)}")
        print(f"Groups:       {len(audit_rows)}")
        print(f"Low groups:   {report['summary']['zero_or_low_groups']}")
        print(f"Prev day ads: {health_report['summary']['previous_day_new_ads']}")
        print(f"7d avg ads:   {health_report['summary']['seven_day_avg_new_ads']}")
        print(f"Save failed:  {health_report['summary']['save_failure_count']}")
        print(f"Incomplete:   {health_report['summary']['incomplete_record_count']}")
        print(f"Reprocess:    {health_report['summary']['reprocess_pending_count']}")
        print(f"Daily plan:   {'triggered' if daily_recovery_plan['should_trigger'] else 'not_needed'}")
        print(f"Report:       {args.json_report}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
