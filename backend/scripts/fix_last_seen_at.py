"""Fix ads with NULL last_seen_at.

Rules:
  - is_still_running == True  -> last_seen_at = today (UTC)
  - is_still_running == False -> last_seen_at = survival_checked_at
  - Neither available         -> last_seen_at = updated_at

Run from the backend directory:
    cd backend
    python scripts/fix_last_seen_at.py
"""

import sys

sys.path.insert(0, ".")

from datetime import datetime, timezone

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


def main():
    session = SyncSessionLocal()
    try:
        # Count ads with NULL last_seen_at
        ads = session.query(Ad).filter(Ad.last_seen_at == None).all()  # noqa: E711
        total = len(ads)
        total_all = session.query(Ad).count()

        print(f"Total ads in database: {total_all}")
        print(f"Ads with NULL last_seen_at: {total}")

        if total == 0:
            print("No ads to fix. Exiting.")
            return

        now = datetime.now(timezone.utc)
        fixed = 0
        method_counts = {"running_today": 0, "survival_checked": 0, "updated_at": 0}

        for ad in ads:
            meta = ad.ad_metadata or {}
            is_running = meta.get("is_still_running")
            survival_checked_at = meta.get("survival_checked_at")

            if is_running is True:
                # Still running -> set to today
                ad.last_seen_at = now
                method_counts["running_today"] += 1
            elif is_running is False and survival_checked_at:
                # Stopped -> use survival_checked_at
                try:
                    checked_dt = datetime.fromisoformat(
                        survival_checked_at.replace("Z", "+00:00")
                    )
                    ad.last_seen_at = checked_dt
                except (ValueError, TypeError):
                    ad.last_seen_at = ad.updated_at
                    method_counts["updated_at"] += 1
                    fixed += 1
                    continue
                method_counts["survival_checked"] += 1
            else:
                # Fallback -> use updated_at
                ad.last_seen_at = ad.updated_at
                method_counts["updated_at"] += 1

            fixed += 1

            if fixed <= 10:
                source = (
                    "running_today"
                    if is_running is True
                    else (
                        "survival_checked"
                        if is_running is False and survival_checked_at
                        else "updated_at"
                    )
                )
                print(
                    f"  [{ad.id}] last_seen_at = {ad.last_seen_at.isoformat()} ({source})"
                )
            elif fixed == 11:
                print(f"  ... (showing first 10 of {total})")

        session.commit()

        # Verify
        remaining = session.query(Ad).filter(Ad.last_seen_at == None).count()  # noqa: E711

        print()
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"Fixed: {fixed}")
        print(f"  via is_still_running=True (today): {method_counts['running_today']}")
        print(f"  via survival_checked_at:           {method_counts['survival_checked']}")
        print(f"  via updated_at (fallback):         {method_counts['updated_at']}")
        print(f"Remaining NULL last_seen_at: {remaining}")

        if remaining == 0:
            print("All ads now have last_seen_at set.")
        else:
            print(f"WARNING: {remaining} ads still have NULL last_seen_at.")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
