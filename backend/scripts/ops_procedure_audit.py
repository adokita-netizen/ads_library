"""A87 (CI-119): Operations procedure audit — automated staleness check.

Scans operational scripts and checks when they were last run (via batch_history),
last modified (git), and flags procedures that may be outdated.

Usage:
    python -m scripts.ops_procedure_audit
    python -m scripts.ops_procedure_audit --json-report exports/ops_audit.json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

SCRIPTS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "scripts")
HISTORY_FILE = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "exports", "batch_history.jsonl"
)

# Key operational scripts that should be run regularly
CRITICAL_SCRIPTS = {
    "aggregate_metrics.py": {"expected_frequency": "daily", "max_stale_days": 3},
    "check_data_integrity.py": {"expected_frequency": "weekly", "max_stale_days": 10},
    "check_ad_survival.py": {"expected_frequency": "weekly", "max_stale_days": 10},
    "migration_precheck.py": {"expected_frequency": "before_migration", "max_stale_days": None},
    "check_secrets.py": {"expected_frequency": "weekly", "max_stale_days": 10},
    "validate_metadata_schema.py": {"expected_frequency": "weekly", "max_stale_days": 10},
    "detect_metric_anomalies.py": {"expected_frequency": "daily", "max_stale_days": 3},
    "export_ads_csv.py": {"expected_frequency": "weekly", "max_stale_days": 14},
}


def get_git_last_modified(filepath: str) -> str | None:
    """Get the last git commit date for a file."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%aI", "--", filepath],
            capture_output=True, text=True, timeout=5,
            cwd=os.path.dirname(filepath),
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except Exception:
        pass
    return None


def get_last_run(script_name: str) -> str | None:
    """Check batch_history.jsonl for last run of this script."""
    job_name = script_name.replace(".py", "")
    last_run = None
    try:
        with open(HISTORY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                try:
                    record = json.loads(line.strip())
                    if record.get("job_name", "").endswith(job_name):
                        last_run = record.get("started_at")
                except json.JSONDecodeError:
                    continue
    except FileNotFoundError:
        pass
    return last_run


def audit_scripts() -> list[dict]:
    """Audit all scripts in the scripts directory."""
    results = []

    for filename in sorted(os.listdir(SCRIPTS_DIR)):
        if not filename.endswith(".py") or filename.startswith("__"):
            continue

        filepath = os.path.join(SCRIPTS_DIR, filename)
        file_stat = os.stat(filepath)
        file_modified = datetime.fromtimestamp(file_stat.st_mtime, tz=timezone.utc)

        entry = {
            "script": filename,
            "file_modified": file_modified.isoformat(),
            "file_size_kb": round(file_stat.st_size / 1024, 1),
        }

        # Git last modified
        git_date = get_git_last_modified(filepath)
        if git_date:
            entry["git_last_modified"] = git_date

        # Check if critical
        if filename in CRITICAL_SCRIPTS:
            info = CRITICAL_SCRIPTS[filename]
            entry["critical"] = True
            entry["expected_frequency"] = info["expected_frequency"]

            last_run = get_last_run(filename)
            entry["last_run"] = last_run

            if info["max_stale_days"] and last_run:
                run_date = datetime.fromisoformat(last_run)
                days_since = (datetime.now(timezone.utc) - run_date).days
                entry["days_since_run"] = days_since
                if days_since > info["max_stale_days"]:
                    entry["status"] = "STALE"
                else:
                    entry["status"] = "OK"
            elif info["max_stale_days"] and not last_run:
                entry["status"] = "NEVER_RUN"
            else:
                entry["status"] = "OK"
        else:
            entry["critical"] = False
            entry["status"] = "OK"

        results.append(entry)

    return results


def main():
    parser = argparse.ArgumentParser(description="Operations procedure audit")
    parser.add_argument("--json-report", type=str, help="Export audit to JSON")
    args = parser.parse_args()

    print("=" * 60)
    print("  Operations Procedure Audit")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    results = audit_scripts()

    critical = [r for r in results if r.get("critical")]
    stale = [r for r in critical if r.get("status") in ("STALE", "NEVER_RUN")]

    print(f"\n  Total scripts: {len(results)}")
    print(f"  Critical scripts: {len(critical)}")
    print(f"  Stale/never-run: {len(stale)}")

    print("\n  Critical Script Status:")
    for r in critical:
        icon = {"OK": "OK", "STALE": "!!", "NEVER_RUN": "--"}.get(r["status"], "??")
        freq = r.get("expected_frequency", "")
        days = r.get("days_since_run", "")
        days_str = f" ({days}d ago)" if days != "" else ""
        print(f"    [{icon}] {r['script']:40s} {freq:20s}{days_str}")

    if stale:
        print("\n  Action needed:")
        for r in stale:
            if r["status"] == "NEVER_RUN":
                print(f"    - {r['script']}: Never recorded in batch history")
            else:
                print(f"    - {r['script']}: {r.get('days_since_run', '?')} days since last run")

    if args.json_report:
        report = {
            "audited_at": datetime.now(timezone.utc).isoformat(),
            "total_scripts": len(results),
            "critical_count": len(critical),
            "stale_count": len(stale),
            "scripts": results,
        }
        os.makedirs(os.path.dirname(args.json_report) or ".", exist_ok=True)
        with open(args.json_report, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=2)
        print(f"\n  Exported: {args.json_report}")

    print()


if __name__ == "__main__":
    main()
