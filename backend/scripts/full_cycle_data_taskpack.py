"""Run A45 full-cycle data taskpack."""

from __future__ import annotations

import argparse
import json
from datetime import date

from app.core.database import SyncSessionLocal
from app.services.full_cycle_data_taskpack import run_full_cycle_data_taskpack


def main() -> None:
    parser = argparse.ArgumentParser(description="Run full-cycle data taskpack")
    parser.add_argument("--date", type=str, help="Target date YYYY-MM-DD")
    parser.add_argument("--target-min-ads-per-day", type=int, default=100)
    parser.add_argument("--focus-keywords", type=str, default="")
    parser.add_argument("--queue-recrawls", action="store_true")
    args = parser.parse_args()

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    focus_keywords = [item.strip() for item in str(args.focus_keywords or "").split(",") if item.strip()]

    session = SyncSessionLocal()
    try:
        result = run_full_cycle_data_taskpack(
            session,
            target_date=target_date,
            focus_keywords=focus_keywords,
            target_min_ads_per_day=int(args.target_min_ads_per_day),
            queue_recrawls=bool(args.queue_recrawls),
        )
        session.commit()
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        session.close()


if __name__ == "__main__":
    main()
