"""A-R2-3: Full data pipeline runner.

Runs all data quality and analysis scripts in sequence against all ads.
Designed for post-crawl execution to ensure 100% data completeness.

Usage:
    python -m scripts.run_full_pipeline              # run all steps
    python -m scripts.run_full_pipeline --step 3     # run from step 3
    python -m scripts.run_full_pipeline --dry-run    # show steps only
"""

import argparse
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Pipeline steps in order
PIPELINE_STEPS = [
    {
        "name": "classify_ads",
        "description": "Classify ads by category",
        "command": [sys.executable, "-m", "scripts.classify_ads"],
    },
    {
        "name": "fix_titles",
        "description": "Fix NULL/empty titles",
        "command": [sys.executable, "-m", "scripts.fix_titles"],
    },
    {
        "name": "fix_destination_urls",
        "description": "Fix destination URLs",
        "command": [sys.executable, "-m", "scripts.fix_destination_urls"],
    },
    {
        "name": "collect_delivery_dates",
        "description": "Collect delivery dates from metadata",
        "command": [sys.executable, "-m", "scripts.collect_delivery_dates"],
    },
    {
        "name": "check_ad_survival",
        "description": "Check ad survival status",
        "command": [
            sys.executable,
            "-m",
            "scripts.check_ad_survival",
            "--max-page-ids",
            "50",
            "--max-snapshot-checks",
            "300",
            "--max-seconds",
            "240",
            "--request-delay",
            "0.5",
            "--snapshot-delay",
            "0.1",
        ],
    },
    {
        "name": "r2_data_quality_fix",
        "description": "Fix metadata gaps (days_running, longevity_class, etc)",
        "command": [sys.executable, "-m", "scripts.r2_data_quality_fix", "--fix"],
    },
    {
        "name": "backfill_deltas",
        "description": "Backfill view/spend increase deltas",
        "command": [sys.executable, "-m", "scripts.backfill_deltas", "--execute"],
    },
    {
        "name": "aggregate_metrics",
        "description": "Aggregate ranking metrics",
        "command": [sys.executable, "-m", "scripts.aggregate_metrics"],
    },
    {
        "name": "validate_metadata_schema",
        "description": "Validate metadata completeness",
        "command": [sys.executable, "-m", "scripts.validate_metadata_schema"],
    },
    {
        "name": "check_data_integrity",
        "description": "Check data integrity",
        "command": [sys.executable, "-m", "scripts.check_data_integrity"],
    },
]


def run_step(step: dict, step_num: int) -> dict:
    """Run a single pipeline step. Returns result dict."""
    start = time.monotonic()
    print(f"\n  [{step_num}/{len(PIPELINE_STEPS)}] {step['name']}: {step['description']}")

    try:
        result = subprocess.run(
            step["command"],
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            timeout=300,  # 5 min per step
            env={**os.environ, "PYTHONIOENCODING": "utf-8"},
        )
        elapsed = round(time.monotonic() - start, 1)
        success = result.returncode == 0

        # Show last 3 lines of output
        output_lines = (result.stdout or "").strip().split("\n")
        for line in output_lines[-3:]:
            if line.strip():
                print(f"    > {line.strip()}")

        if not success and result.stderr:
            error_lines = result.stderr.strip().split("\n")
            for line in error_lines[-3:]:
                if line.strip():
                    print(f"    ! {line.strip()}")

        status = "OK" if success else "FAILED"
        print(f"    [{status}] ({elapsed}s)")

        return {
            "name": step["name"],
            "status": status,
            "duration_seconds": elapsed,
            "returncode": result.returncode,
        }

    except subprocess.TimeoutExpired:
        elapsed = round(time.monotonic() - start, 1)
        print(f"    [TIMEOUT] ({elapsed}s)")
        return {"name": step["name"], "status": "TIMEOUT", "duration_seconds": elapsed}
    except Exception as e:
        elapsed = round(time.monotonic() - start, 1)
        print(f"    [ERROR] {e}")
        return {"name": step["name"], "status": "ERROR", "error": str(e), "duration_seconds": elapsed}


def main():
    parser = argparse.ArgumentParser(description="Full data pipeline runner")
    parser.add_argument("--step", type=int, default=1, help="Start from step N (default: 1)")
    parser.add_argument("--dry-run", action="store_true", help="Show steps without running")
    args = parser.parse_args()

    print("=" * 60)
    print("  A-R2-3: Full Data Pipeline")
    print(f"  {datetime.now(timezone.utc).isoformat()}")
    print(f"  Steps: {len(PIPELINE_STEPS)}")
    print("=" * 60)

    if args.dry_run:
        for i, step in enumerate(PIPELINE_STEPS, 1):
            skip = " (SKIP)" if i < args.step else ""
            print(f"  {i}. {step['name']}: {step['description']}{skip}")
        print("\n  DRY-RUN. No scripts executed.")
        return

    results = []
    total_start = time.monotonic()

    for i, step in enumerate(PIPELINE_STEPS, 1):
        if i < args.step:
            print(f"\n  [{i}/{len(PIPELINE_STEPS)}] {step['name']}: SKIPPED (--step {args.step})")
            continue
        result = run_step(step, i)
        results.append(result)

    total_elapsed = round(time.monotonic() - total_start, 1)

    # Summary
    print("\n" + "=" * 60)
    print("  Pipeline Summary")
    print("=" * 60)
    ok = sum(1 for r in results if r["status"] == "OK")
    failed = sum(1 for r in results if r["status"] != "OK")
    print(f"  OK: {ok}  Failed: {failed}  Total time: {total_elapsed}s")

    if failed:
        print("\n  Failed steps:")
        for r in results:
            if r["status"] != "OK":
                print(f"    - {r['name']}: {r['status']}")

    print()


if __name__ == "__main__":
    main()
