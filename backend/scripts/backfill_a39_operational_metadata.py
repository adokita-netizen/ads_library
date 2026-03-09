"""A39: backfill standardized freshness / LP metadata keys for existing ads.

Usage:
    python -m scripts.backfill_a39_operational_metadata
    python -m scripts.backfill_a39_operational_metadata --execute
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad, normalize_operational_metadata


def backfill_a39_operational_metadata(session, *, limit: int = 0, execute: bool = False) -> dict:
    query = session.query(Ad).order_by(Ad.id.asc())
    if limit and limit > 0:
        query = query.limit(limit)

    ads = query.all()
    updated = 0
    samples = []
    for ad in ads:
        before = dict(ad.ad_metadata or {})
        normalize_operational_metadata(ad)
        after = dict(ad.ad_metadata or {})
        if before != after:
            updated += 1
            if execute:
                flag_modified(ad, "ad_metadata")
            if len(samples) < 20:
                samples.append(
                    {
                        "ad_id": ad.id,
                        "before_keys": sorted(before.keys()),
                        "after_keys": sorted(after.keys()),
                    }
                )

    if execute and updated:
        session.commit()
    elif not execute:
        session.rollback()

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_ads": len(ads),
        "updated_ads": updated,
        "execute": execute,
        "samples": samples,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill A39 operational metadata keys")
    parser.add_argument("--execute", action="store_true", help="Persist normalized metadata")
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--json-report", type=str)
    args = parser.parse_args()

    session = SyncSessionLocal()
    try:
        report = backfill_a39_operational_metadata(
            session,
            limit=args.limit,
            execute=args.execute,
        )
    finally:
        session.close()

    print(f"total_ads:     {report['total_ads']}")
    print(f"updated_ads:   {report['updated_ads']}")
    print(f"mode:          {'execute' if args.execute else 'dry-run'}")

    if args.json_report:
        with open(args.json_report, "w", encoding="utf-8") as fh:
            json.dump(report, fh, ensure_ascii=False, indent=2)
        print(f"report:        {args.json_report}")


if __name__ == "__main__":
    main()
