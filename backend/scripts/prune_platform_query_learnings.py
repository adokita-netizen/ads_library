"""Prune weak/stale platform query learning entries.

Usage:
  python -m scripts.prune_platform_query_learnings
  python -m scripts.prune_platform_query_learnings --min-attempts 5 --min-success-rate 0.2 --stale-days 21
"""

import argparse

from app.api.endpoints.rankings import (
    _count_learning_entries,
    _load_platform_query_learnings,
    _prune_platform_query_learnings,
    _save_platform_query_learnings,
)


def main():
    parser = argparse.ArgumentParser(description="Prune platform query learning dictionary")
    parser.add_argument("--min-attempts", type=int, default=3)
    parser.add_argument("--min-success-rate", type=float, default=0.15)
    parser.add_argument("--stale-days", type=int, default=14)
    args = parser.parse_args()

    data = _load_platform_query_learnings()
    before = _count_learning_entries(data)
    pruned, stats = _prune_platform_query_learnings(
        data,
        min_attempts=max(1, int(args.min_attempts)),
        min_success_rate=max(0.0, min(1.0, float(args.min_success_rate))),
        stale_days=max(1, int(args.stale_days)),
    )
    _save_platform_query_learnings(pruned)
    after = _count_learning_entries(pruned)

    print(f"Learning entries before: {before}")
    print(f"Learning entries after:  {after}")
    print(f"Removed: {int(stats.get('removed') or 0)}")
    print(f"Kept:    {int(stats.get('kept') or 0)}")


if __name__ == "__main__":
    main()

