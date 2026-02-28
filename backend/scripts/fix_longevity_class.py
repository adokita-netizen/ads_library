"""Fix ads with missing longevity_class in ad_metadata.

Classification based on days_running:
  - 0-7 days:   "flash"
  - 8-30 days:  "short"
  - 31-90 days: "medium"
  - 91+ days:   "long"

If days_running is not available, it is estimated from first_seen_at.

Run from the backend directory:
    cd backend
    python scripts/fix_longevity_class.py
"""

import sys

sys.path.insert(0, ".")

from datetime import datetime, timezone

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


def classify_longevity(days: int) -> str:
    """Classify ad longevity based on days running."""
    if days >= 91:
        return "long"
    elif days >= 31:
        return "medium"
    elif days >= 8:
        return "short"
    else:
        return "flash"


def main():
    session = SyncSessionLocal()
    try:
        total_all = session.query(Ad).count()
        print(f"Total ads in database: {total_all}")

        # Find ads without longevity_class in metadata
        all_ads = session.query(Ad).all()
        ads_missing = [
            ad for ad in all_ads
            if not (ad.ad_metadata or {}).get("longevity_class")
        ]
        total = len(ads_missing)
        print(f"Ads missing longevity_class: {total}")

        if total == 0:
            print("No ads to fix. Exiting.")
            return

        now = datetime.now(timezone.utc)
        fixed = 0
        class_counts = {"flash": 0, "short": 0, "medium": 0, "long": 0}
        source_counts = {"days_running": 0, "first_seen_at": 0, "fallback": 0}

        for ad in ads_missing:
            meta = dict(ad.ad_metadata or {})
            days = meta.get("days_running")
            source = "days_running"

            if days is None:
                # Estimate from first_seen_at
                if ad.first_seen_at:
                    first = ad.first_seen_at
                    if first.tzinfo is None:
                        first = first.replace(tzinfo=timezone.utc)
                    end = ad.last_seen_at or now
                    if end.tzinfo is None:
                        end = end.replace(tzinfo=timezone.utc)
                    days = max(1, (end - first).days)
                    meta["days_running"] = days
                    source = "first_seen_at"
                else:
                    # Fallback: use created_at to now
                    created = ad.created_at
                    if created.tzinfo is None:
                        created = created.replace(tzinfo=timezone.utc)
                    days = max(1, (now - created).days)
                    meta["days_running"] = days
                    source = "fallback"

            longevity = classify_longevity(days)
            meta["longevity_class"] = longevity
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

            class_counts[longevity] += 1
            source_counts[source] += 1
            fixed += 1

            if fixed <= 10:
                print(f"  [{ad.id}] days={days} -> {longevity} (source: {source})")
            elif fixed == 11:
                print(f"  ... (showing first 10 of {total})")

            # Commit every 100 ads
            if fixed % 100 == 0:
                session.commit()

        session.commit()

        # Verify
        remaining = sum(
            1 for ad in session.query(Ad).all()
            if not (ad.ad_metadata or {}).get("longevity_class")
        )

        print()
        print("=" * 60)
        print("RESULTS")
        print("=" * 60)
        print(f"Fixed: {fixed}")
        print()
        print("Longevity class distribution (newly assigned):")
        for cls, count in sorted(class_counts.items()):
            print(f"  {cls}: {count}")
        print()
        print("Days source:")
        for src, count in sorted(source_counts.items()):
            print(f"  {src}: {count}")
        print()
        print(f"Remaining without longevity_class: {remaining}")

        if remaining == 0:
            print("All ads now have longevity_class.")
        else:
            print(f"WARNING: {remaining} ads still missing longevity_class.")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
