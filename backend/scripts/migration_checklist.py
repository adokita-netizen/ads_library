"""A86 (CI-103): Auto-generate data migration checklist.

Inspects the current database schema and pending Alembic migrations
to produce a pre-migration checklist covering:
  - Backup verification
  - Schema changes (new tables, columns, indexes)
  - Data volume assessment
  - Rollback plan

Usage:
    python -m scripts.migration_checklist
    python -m scripts.migration_checklist --output checklist.md
"""

import argparse
import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text, inspect as sa_inspect
from app.core.database import SyncSessionLocal, sync_engine


def gather_schema_info(session) -> dict:
    """Gather current schema information for checklist generation."""
    info = {}

    insp = sa_inspect(sync_engine)

    # Tables
    tables = insp.get_table_names(schema="public")
    info["tables"] = tables
    info["table_count"] = len(tables)

    # Table sizes
    sizes = {}
    for table in tables:
        try:
            count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            sizes[table] = count
        except Exception:
            sizes[table] = -1
    info["table_sizes"] = sizes

    # Current Alembic revision
    try:
        if insp.has_table("alembic_version"):
            rev = session.execute(text("SELECT version_num FROM alembic_version")).scalar()
            info["current_revision"] = rev or "none"
        else:
            info["current_revision"] = "no_alembic_table"
    except Exception:
        info["current_revision"] = "unknown"

    # Database size
    try:
        db_size = session.execute(text(
            "SELECT pg_size_pretty(pg_database_size(current_database()))"
        )).scalar()
        info["database_size"] = db_size
    except Exception:
        info["database_size"] = "unknown"

    # Indexes
    try:
        idx_rows = session.execute(text("""
            SELECT tablename, indexname
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
        """)).fetchall()
        info["indexes"] = [(r[0], r[1]) for r in idx_rows]
    except Exception:
        info["indexes"] = []

    return info


def generate_checklist(info: dict) -> str:
    """Generate a markdown checklist from schema info."""
    now = datetime.now(timezone.utc).isoformat()
    large_tables = {k: v for k, v in info["table_sizes"].items() if v > 10000}

    lines = [
        f"# Migration Checklist",
        f"Generated: {now}",
        "",
        "## Pre-Migration",
        "",
        "- [ ] **Backup database**",
        f"  - Current size: {info.get('database_size', 'unknown')}",
        f"  - Current revision: {info.get('current_revision', 'unknown')}",
        "  - `pg_dump -Fc dbname > backup_$(date +%Y%m%d).dump`",
        "",
        "- [ ] **Check active connections**",
        "  - `python -m scripts.migration_precheck`",
        "  - No idle-in-transaction connections",
        "  - No long-running queries",
        "",
        "- [ ] **Review migration SQL**",
        "  - `alembic upgrade head --sql > migration_review.sql`",
        "  - Check for ALTER TABLE on large tables",
        "",
        "- [ ] **Notify team**",
        "  - Expected downtime window",
        "  - Rollback plan communicated",
        "",
        "## Schema Overview",
        "",
        f"Tables: {info['table_count']}",
        "",
    ]

    # Table sizes
    lines.append("| Table | Rows | Notes |")
    lines.append("|-------|------|-------|")
    for table in sorted(info["table_sizes"].keys()):
        count = info["table_sizes"][table]
        notes = ""
        if count > 100000:
            notes = "LARGE — ALTER may lock"
        elif count > 10000:
            notes = "medium"
        lines.append(f"| {table} | {count:,} | {notes} |")

    if large_tables:
        lines.extend([
            "",
            "### Large Table Warnings",
            "",
        ])
        for table, count in large_tables.items():
            lines.append(f"- **{table}** ({count:,} rows): Consider `CREATE INDEX CONCURRENTLY`, "
                         f"avoid `ALTER TABLE ... ADD COLUMN ... DEFAULT`")

    lines.extend([
        "",
        "## During Migration",
        "",
        "- [ ] **Run pre-check**: `python -m scripts.migration_precheck --strict`",
        "- [ ] **Apply migration**: `alembic upgrade head`",
        "- [ ] **Verify**: `alembic current`",
        "- [ ] **Run integrity check**: `python -m scripts.check_data_integrity`",
        "",
        "## Post-Migration",
        "",
        "- [ ] **Verify application health**",
        "  - API responds: `curl /api/health`",
        "  - Key queries work",
        "",
        "- [ ] **Run ANALYZE on modified tables**",
    ])

    if large_tables:
        for table in large_tables:
            lines.append(f"  - `ANALYZE {table};`")

    lines.extend([
        "",
        "- [ ] **Monitor for 30 minutes**",
        "  - Check error rates in CloudWatch",
        "  - Check query performance",
        "",
        "## Rollback Plan",
        "",
        f"- Current revision: `{info.get('current_revision', 'unknown')}`",
        f"- Rollback: `alembic downgrade {info.get('current_revision', '<revision>')}`",
        "- Full restore: `pg_restore -d dbname backup.dump`",
        "",
    ])

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Generate migration checklist")
    parser.add_argument("--output", type=str, help="Output file (default: stdout)")
    args = parser.parse_args()

    session = SyncSessionLocal()
    try:
        info = gather_schema_info(session)
        checklist = generate_checklist(info)

        if args.output:
            os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
            with open(args.output, "w", encoding="utf-8") as f:
                f.write(checklist)
            print(f"Checklist written to: {args.output}")
        else:
            print(checklist)

    finally:
        session.close()


if __name__ == "__main__":
    main()
