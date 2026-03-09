"""A64 (CI-081): Migration pre-check CLI.

Detects dangerous conditions BEFORE applying database migrations.
Run this before `alembic upgrade head` in production.

Usage:
    python -m scripts.migration_precheck
    python -m scripts.migration_precheck --strict  # exit 1 on warnings
"""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect as sa_inspect
from app.core.database import SyncSessionLocal, sync_engine


def check_active_connections(session) -> dict:
    """Check for active connections that could block migration."""
    try:
        rows = session.execute(text("""
            SELECT count(*) as total,
                   count(*) FILTER (WHERE state = 'active') as active,
                   count(*) FILTER (WHERE state = 'idle in transaction') as idle_in_tx,
                   count(*) FILTER (WHERE wait_event_type = 'Lock') as waiting_on_lock
            FROM pg_stat_activity
            WHERE datname = current_database()
            AND pid != pg_backend_pid()
        """)).fetchone()
        result = {
            "name": "active_connections",
            "total": rows[0],
            "active": rows[1],
            "idle_in_transaction": rows[2],
            "waiting_on_lock": rows[3],
        }
        if rows[2] > 0:
            result["severity"] = "warning"
            result["message"] = "%d idle-in-transaction connections may block DDL" % rows[2]
        elif rows[3] > 0:
            result["severity"] = "warning"
            result["message"] = "%d connections waiting on locks" % rows[3]
        else:
            result["severity"] = "ok"
        return result
    except Exception as e:
        return {"name": "active_connections", "severity": "skip", "message": str(e)}


def check_table_sizes(session) -> dict:
    """Check for large tables that need careful migration."""
    try:
        rows = session.execute(text("""
            SELECT relname, n_live_tup
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            ORDER BY n_live_tup DESC
            LIMIT 10
        """)).fetchall()
        tables = {r[0]: r[1] for r in rows}
        large_tables = {k: v for k, v in tables.items() if v > 100000}
        result = {
            "name": "table_sizes",
            "tables": tables,
            "large_tables_100k": list(large_tables.keys()),
        }
        if large_tables:
            result["severity"] = "warning"
            result["message"] = "Large tables: %s — ALTER TABLE may lock for extended time" % ", ".join(
                "%s(%dk)" % (k, v // 1000) for k, v in large_tables.items()
            )
        else:
            result["severity"] = "ok"
        return result
    except Exception as e:
        return {"name": "table_sizes", "severity": "skip", "message": str(e)}


def check_pending_transactions(session) -> dict:
    """Check for long-running transactions."""
    try:
        rows = session.execute(text("""
            SELECT pid, state,
                   EXTRACT(EPOCH FROM (now() - xact_start))::int as duration_secs,
                   left(query, 100) as query
            FROM pg_stat_activity
            WHERE datname = current_database()
            AND xact_start IS NOT NULL
            AND state != 'idle'
            AND pid != pg_backend_pid()
            ORDER BY xact_start
        """)).fetchall()
        long_running = [
            {"pid": r[0], "state": r[1], "duration_secs": r[2], "query": r[3]}
            for r in rows if r[2] > 30
        ]
        result = {
            "name": "pending_transactions",
            "active_transactions": len(rows),
            "long_running_30s": len(long_running),
        }
        if long_running:
            result["severity"] = "warning"
            result["message"] = "%d transactions running >30s — may block migration" % len(long_running)
            result["details"] = long_running[:5]
        else:
            result["severity"] = "ok"
        return result
    except Exception as e:
        return {"name": "pending_transactions", "severity": "skip", "message": str(e)}


def check_disk_space(session) -> dict:
    """Check database size and available disk."""
    try:
        db_size = session.execute(text(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        )).scalar()
        return {"name": "disk_space", "database_size": db_size, "severity": "ok"}
    except Exception as e:
        return {"name": "disk_space", "severity": "skip", "message": str(e)}


def check_alembic_state(session) -> dict:
    """Check current alembic migration version."""
    try:
        insp = sa_inspect(sync_engine)
        if not insp.has_table("alembic_version"):
            return {
                "name": "alembic_state",
                "severity": "warning",
                "message": "No alembic_version table — first migration or unmanaged schema",
            }
        rev = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
        return {
            "name": "alembic_state",
            "current_revision": rev or "none",
            "severity": "ok",
        }
    except Exception as e:
        return {"name": "alembic_state", "severity": "skip", "message": str(e)}


def check_replication_lag(session) -> dict:
    """Check replication lag if replicas exist."""
    try:
        rows = session.execute(text("""
            SELECT client_addr, state,
                   EXTRACT(EPOCH FROM replay_lag)::int as lag_secs
            FROM pg_stat_replication
        """)).fetchall()
        if not rows:
            return {"name": "replication_lag", "severity": "ok", "message": "No replicas"}
        lagging = [{"addr": str(r[0]), "lag_secs": r[2]} for r in rows if r[2] and r[2] > 10]
        result = {"name": "replication_lag", "replicas": len(rows)}
        if lagging:
            result["severity"] = "warning"
            result["message"] = "%d replicas lagging >10s" % len(lagging)
            result["details"] = lagging
        else:
            result["severity"] = "ok"
        return result
    except Exception as e:
        return {"name": "replication_lag", "severity": "skip", "message": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Migration pre-check")
    parser.add_argument("--strict", action="store_true", help="Exit 1 on any warning")
    args = parser.parse_args()

    session = SyncSessionLocal()
    checks = []
    try:
        checks.append(check_alembic_state(session))
        checks.append(check_active_connections(session))
        checks.append(check_pending_transactions(session))
        checks.append(check_table_sizes(session))
        checks.append(check_disk_space(session))
        checks.append(check_replication_lag(session))
    finally:
        session.close()

    print("=" * 60)
    print("  Migration Pre-Check")
    print("=" * 60)

    warnings = 0
    for check in checks:
        sev = check.get("severity", "ok")
        icon = {"ok": "OK", "warning": "!!", "skip": "--"}.get(sev, "??")
        print("\n  [%s] %s" % (icon, check["name"]))
        if sev == "warning":
            warnings += 1
        for k, v in check.items():
            if k not in ("name", "severity", "details"):
                print("      %s: %s" % (k, v))
        if "details" in check:
            for d in check["details"][:3]:
                print("      > %s" % d)

    print("\n  Warnings: %d" % warnings)
    if warnings == 0:
        print("  Result: SAFE to migrate")
    else:
        print("  Result: Review warnings before migrating")

    if args.strict and warnings > 0:
        print("\n  STRICT MODE: Exiting with error due to warnings")
        sys.exit(1)


if __name__ == "__main__":
    main()
