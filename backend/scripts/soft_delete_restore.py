"""A84 (CI-111): Soft-delete and restore procedures for main tables.

Provides safe delete/restore operations for ads and their related data.
Soft-deleted ads are marked with status='deleted' and can be restored.

Usage:
    python -m scripts.soft_delete_restore delete --ad-ids 123 456   # soft-delete
    python -m scripts.soft_delete_restore restore --ad-ids 123 456  # restore
    python -m scripts.soft_delete_restore list-deleted              # show deleted
    python -m scripts.soft_delete_restore purge --older-than 90     # hard-delete old
"""

import argparse
import os
import sys
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad


def soft_delete_ads(session, ad_ids: list[int]) -> dict:
    """Mark ads as soft-deleted. Preserves all data for recovery."""
    deleted = 0
    not_found = []
    already_deleted = []

    for ad_id in ad_ids:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            not_found.append(ad_id)
            continue

        # Check if already deleted
        meta = dict(ad.ad_metadata or {})
        if meta.get("_soft_deleted"):
            already_deleted.append(ad_id)
            continue

        # Store original status for restore
        original_status = ad.status.value if hasattr(ad.status, "value") else str(ad.status) if ad.status else None
        meta["_soft_deleted"] = True
        meta["_deleted_at"] = datetime.now(timezone.utc).isoformat()
        meta["_original_status"] = original_status

        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")

        # Set status to indicate deletion
        from app.models.ad import AdStatusEnum
        ad.status = AdStatusEnum.inactive
        deleted += 1

    if deleted > 0:
        session.commit()

    return {
        "deleted": deleted,
        "not_found": not_found,
        "already_deleted": already_deleted,
    }


def restore_ads(session, ad_ids: list[int]) -> dict:
    """Restore soft-deleted ads."""
    restored = 0
    not_found = []
    not_deleted = []

    for ad_id in ad_ids:
        ad = session.query(Ad).filter(Ad.id == ad_id).first()
        if not ad:
            not_found.append(ad_id)
            continue

        meta = dict(ad.ad_metadata or {})
        if not meta.get("_soft_deleted"):
            not_deleted.append(ad_id)
            continue

        # Restore original status
        original_status = meta.pop("_original_status", None)
        meta.pop("_soft_deleted", None)
        meta.pop("_deleted_at", None)

        ad.ad_metadata = meta
        flag_modified(ad, "ad_metadata")

        if original_status:
            from app.models.ad import AdStatusEnum
            try:
                ad.status = AdStatusEnum(original_status)
            except (ValueError, KeyError):
                ad.status = AdStatusEnum.active

        restored += 1

    if restored > 0:
        session.commit()

    return {
        "restored": restored,
        "not_found": not_found,
        "not_deleted": not_deleted,
    }


def list_deleted(session) -> list[dict]:
    """List all soft-deleted ads."""
    ads = session.query(Ad).all()
    deleted = []
    for ad in ads:
        meta = ad.ad_metadata or {}
        if meta.get("_soft_deleted"):
            deleted.append({
                "id": ad.id,
                "title": (ad.title or "")[:50],
                "advertiser": ad.advertiser_name or "",
                "deleted_at": meta.get("_deleted_at", "unknown"),
                "original_status": meta.get("_original_status", "unknown"),
            })
    return deleted


def purge_old_deleted(session, older_than_days: int) -> int:
    """Permanently delete ads that were soft-deleted more than N days ago."""
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    cutoff_str = cutoff.isoformat()

    ads = session.query(Ad).all()
    to_purge = []
    for ad in ads:
        meta = ad.ad_metadata or {}
        deleted_at = meta.get("_deleted_at", "")
        if meta.get("_soft_deleted") and deleted_at and deleted_at < cutoff_str:
            to_purge.append(ad.id)

    if not to_purge:
        return 0

    # Delete related metrics first
    session.execute(text(
        "DELETE FROM ad_daily_metrics WHERE ad_id = ANY(:ids)"
    ), {"ids": to_purge})

    # Delete product_rankings if exists
    try:
        session.execute(text(
            "DELETE FROM product_rankings WHERE ad_id = ANY(:ids)"
        ), {"ids": to_purge})
    except Exception:
        pass

    # Delete ads
    session.execute(text(
        "DELETE FROM ads WHERE id = ANY(:ids)"
    ), {"ids": to_purge})

    session.commit()
    return len(to_purge)


def main():
    parser = argparse.ArgumentParser(description="Soft-delete and restore ads")
    sub = parser.add_subparsers(dest="command")

    delete_p = sub.add_parser("delete", help="Soft-delete ads")
    delete_p.add_argument("--ad-ids", nargs="+", type=int, required=True)

    restore_p = sub.add_parser("restore", help="Restore soft-deleted ads")
    restore_p.add_argument("--ad-ids", nargs="+", type=int, required=True)

    sub.add_parser("list-deleted", help="List soft-deleted ads")

    purge_p = sub.add_parser("purge", help="Permanently delete old soft-deleted ads")
    purge_p.add_argument("--older-than", type=int, default=90,
                         help="Days since soft-deletion (default: 90)")
    purge_p.add_argument("--execute", action="store_true",
                         help="Actually purge (default: dry-run)")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    session = SyncSessionLocal()
    try:
        if args.command == "delete":
            result = soft_delete_ads(session, args.ad_ids)
            print(f"Soft-deleted: {result['deleted']}")
            if result["not_found"]:
                print(f"Not found: {result['not_found']}")
            if result["already_deleted"]:
                print(f"Already deleted: {result['already_deleted']}")

        elif args.command == "restore":
            result = restore_ads(session, args.ad_ids)
            print(f"Restored: {result['restored']}")
            if result["not_found"]:
                print(f"Not found: {result['not_found']}")
            if result["not_deleted"]:
                print(f"Not deleted: {result['not_deleted']}")

        elif args.command == "list-deleted":
            deleted = list_deleted(session)
            if not deleted:
                print("No soft-deleted ads.")
            else:
                print(f"Soft-deleted ads: {len(deleted)}")
                for d in deleted:
                    print(f"  ID={d['id']} deleted={d['deleted_at'][:10]} {d['advertiser'][:30]}")

        elif args.command == "purge":
            if not args.execute:
                # Dry run: just count
                deleted = list_deleted(session)
                cutoff = datetime.now(timezone.utc) - timedelta(days=args.older_than)
                eligible = [d for d in deleted if d["deleted_at"] < cutoff.isoformat()]
                print(f"Would purge {len(eligible)} ads (deleted >{args.older_than} days ago)")
                print("Use --execute to proceed.")
            else:
                count = purge_old_deleted(session, args.older_than)
                print(f"Purged {count} ads permanently.")

    finally:
        session.close()


if __name__ == "__main__":
    main()
