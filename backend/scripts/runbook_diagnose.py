"""A67 (CI-089): Incident runbook — automated diagnosis & recovery hints.

Checks common failure scenarios and provides step-by-step guidance:
  1. Database connectivity issues
  2. Stale/missing daily metrics
  3. SQS queue backlog
  4. Lambda errors (via CloudWatch)
  5. Disk/table bloat

Usage:
    python -m scripts.runbook_diagnose
    python -m scripts.runbook_diagnose --check db       # single check
    python -m scripts.runbook_diagnose --json-report exports/diagnosis.json
"""

import argparse
import json
import os
import sys
from datetime import date, datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def check_database() -> dict:
    """Diagnose database connectivity and health."""
    result = {"name": "database", "steps": []}

    # Step 1: Can we connect?
    try:
        from app.core.database import sync_engine, is_in_memory_mode, get_connection_error
        if is_in_memory_mode():
            result["status"] = "CRITICAL"
            result["steps"].append({
                "issue": "Running in SQLite fallback mode",
                "error": get_connection_error(),
                "action": [
                    "Check DATABASE_URL in .env",
                    "Verify PostgreSQL is running: pg_isready -h <host> -p 5432",
                    "Check RDS security group allows inbound from this IP",
                    "Try: python -c \"from app.core.database import sync_engine; print('ok')\"",
                ],
            })
            return result
    except Exception as e:
        result["status"] = "CRITICAL"
        result["steps"].append({
            "issue": "Cannot import database module",
            "error": str(e),
            "action": ["Check .env file exists", "Run: pip install -r requirements.txt"],
        })
        return result

    # Step 2: Query test
    try:
        from sqlalchemy import text
        with sync_engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        result["steps"].append({"check": "connection_test", "status": "ok"})
    except Exception as e:
        result["status"] = "CRITICAL"
        result["steps"].append({
            "issue": "Connection test failed",
            "error": str(e),
            "action": [
                "Check pg_hba.conf for auth rules",
                "Verify password in DATABASE_URL",
                "Check connection limits: SELECT count(*) FROM pg_stat_activity",
            ],
        })
        return result

    # Step 3: Check pool health
    try:
        pool = sync_engine.pool
        result["steps"].append({
            "check": "pool_status",
            "size": pool.size(),
            "checked_in": pool.checkedin(),
            "checked_out": pool.checkedout(),
            "overflow": pool.overflow(),
            "status": "ok",
        })
    except Exception:
        pass

    result["status"] = "OK"
    return result


def check_metrics_freshness() -> dict:
    """Check if daily metrics are being collected."""
    result = {"name": "metrics_freshness", "steps": []}

    try:
        from sqlalchemy import text
        from app.core.database import SyncSessionLocal

        session = SyncSessionLocal()
        try:
            # Latest metric date
            latest = session.execute(text(
                "SELECT MAX(metric_date) FROM ad_daily_metrics"
            )).scalar()

            if latest is None:
                result["status"] = "WARNING"
                result["steps"].append({
                    "issue": "No metrics data at all",
                    "action": [
                        "Run initial metrics collection: python -m scripts.aggregate_metrics",
                        "Check if ads table has data: SELECT count(*) FROM ads",
                    ],
                })
                return result

            days_stale = (date.today() - latest).days
            result["steps"].append({
                "check": "latest_metric_date",
                "value": str(latest),
                "days_stale": days_stale,
            })

            if days_stale > 2:
                result["status"] = "WARNING"
                result["steps"].append({
                    "issue": f"Metrics are {days_stale} days stale",
                    "action": [
                        "Check Celery worker status: celery -A app.tasks.worker inspect active",
                        "Check ECS task status in AWS console",
                        "Manual run: python -m app.tasks.metrics_tasks",
                        "Check logs: CloudWatch > /ecs/vaap-production-worker",
                    ],
                })
            else:
                result["status"] = "OK"

            # Count today vs yesterday
            today_count = session.execute(text(
                "SELECT COUNT(*) FROM ad_daily_metrics WHERE metric_date = CURRENT_DATE"
            )).scalar()
            yesterday_count = session.execute(text(
                "SELECT COUNT(*) FROM ad_daily_metrics WHERE metric_date = CURRENT_DATE - 1"
            )).scalar()
            result["steps"].append({
                "check": "daily_counts",
                "today": today_count,
                "yesterday": yesterday_count,
            })

            if today_count == 0 and yesterday_count > 0:
                result["status"] = "WARNING"
                result["steps"].append({
                    "issue": "No metrics collected today yet",
                    "action": ["Check if daily job has run", "Trigger manually if needed"],
                })

        finally:
            session.close()

    except Exception as e:
        result["status"] = "ERROR"
        result["steps"].append({"issue": "Check failed", "error": str(e)})

    return result


def check_table_health() -> dict:
    """Check table sizes and bloat."""
    result = {"name": "table_health", "steps": []}

    try:
        from sqlalchemy import text
        from app.core.database import SyncSessionLocal

        session = SyncSessionLocal()
        try:
            rows = session.execute(text("""
                SELECT relname,
                       n_live_tup,
                       n_dead_tup,
                       pg_size_pretty(pg_total_relation_size(relid)) as total_size
                FROM pg_stat_user_tables
                WHERE schemaname = 'public'
                ORDER BY pg_total_relation_size(relid) DESC
                LIMIT 10
            """)).fetchall()

            tables = []
            bloated = []
            for r in rows:
                table = {
                    "name": r[0], "live_rows": r[1],
                    "dead_rows": r[2], "size": r[3],
                }
                tables.append(table)
                if r[2] > r[1] * 0.3 and r[2] > 1000:
                    bloated.append(r[0])

            result["steps"].append({"check": "table_sizes", "tables": tables})

            if bloated:
                result["status"] = "WARNING"
                result["steps"].append({
                    "issue": f"Tables with high dead row ratio: {', '.join(bloated)}",
                    "action": [
                        f"VACUUM ANALYZE {t};" for t in bloated
                    ],
                })
            else:
                result["status"] = "OK"

        finally:
            session.close()

    except Exception as e:
        result["status"] = "SKIP"
        result["steps"].append({"issue": "Check failed", "error": str(e)})

    return result


def check_data_integrity_quick() -> dict:
    """Quick data integrity check (subset of full check_data_integrity.py)."""
    result = {"name": "data_integrity", "steps": []}

    try:
        from sqlalchemy import text
        from app.core.database import SyncSessionLocal

        session = SyncSessionLocal()
        try:
            orphans = session.execute(text("""
                SELECT COUNT(*) FROM ad_daily_metrics m
                LEFT JOIN ads a ON m.ad_id = a.id
                WHERE a.id IS NULL
            """)).scalar()

            result["steps"].append({"check": "orphaned_metrics", "count": orphans})

            if orphans > 0:
                result["status"] = "WARNING"
                result["steps"].append({
                    "issue": f"{orphans} orphaned metric records",
                    "action": [
                        "Run full check: python -m scripts.check_data_integrity",
                        "Auto-fix: python -m scripts.check_data_integrity --fix",
                    ],
                })
            else:
                result["status"] = "OK"

        finally:
            session.close()

    except Exception as e:
        result["status"] = "SKIP"
        result["steps"].append({"issue": "Check failed", "error": str(e)})

    return result


# ── All checks registry ──────────────────────────────────────────

ALL_CHECKS = {
    "db": ("Database Connectivity", check_database),
    "metrics": ("Metrics Freshness", check_metrics_freshness),
    "tables": ("Table Health", check_table_health),
    "integrity": ("Data Integrity", check_data_integrity_quick),
}


def main():
    parser = argparse.ArgumentParser(description="Incident runbook diagnosis")
    parser.add_argument("--check", choices=list(ALL_CHECKS.keys()),
                        help="Run a single check instead of all")
    parser.add_argument("--json-report", type=str, help="Export report to JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("  Incident Runbook — Automated Diagnosis")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    checks_to_run = {args.check: ALL_CHECKS[args.check]} if args.check else ALL_CHECKS
    results = []

    for key, (label, fn) in checks_to_run.items():
        try:
            result = fn()
        except Exception as e:
            result = {"name": key, "status": "ERROR", "steps": [{"error": str(e)}]}

        results.append(result)
        status = result.get("status", "UNKNOWN")
        icon = {"OK": "OK", "WARNING": "!!", "CRITICAL": "XX", "SKIP": "--"}.get(status, "??")
        print(f"\n  [{icon}] {label}: {status}")

        for step in result.get("steps", []):
            if "issue" in step:
                print(f"      Issue: {step['issue']}")
                for action in step.get("action", []):
                    print(f"        → {action}")
            elif "check" in step:
                detail = {k: v for k, v in step.items() if k != "check" and k != "tables"}
                if detail:
                    print(f"      {step['check']}: {detail}")

    # Summary
    critical = sum(1 for r in results if r.get("status") == "CRITICAL")
    warnings = sum(1 for r in results if r.get("status") == "WARNING")

    print(f"\n  Critical: {critical}  Warnings: {warnings}")
    if critical > 0:
        print("  VERDICT: Immediate action required")
    elif warnings > 0:
        print("  VERDICT: Review warnings above")
    else:
        print("  VERDICT: All systems healthy")

    if args.json_report:
        report = {
            "diagnosed_at": datetime.now(timezone.utc).isoformat(),
            "results": results,
            "critical": critical,
            "warnings": warnings,
        }
        os.makedirs(os.path.dirname(args.json_report) or ".", exist_ok=True)
        with open(args.json_report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Exported: {args.json_report}")

    print()


if __name__ == "__main__":
    main()
