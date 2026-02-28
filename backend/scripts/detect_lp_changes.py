#!/usr/bin/env python3
"""Detect landing page changes by hashing LP content.

For ads with LP URLs:
  - Hash current LP content (from cached HTML if available)
  - Compare with previous hash (stored in data/lp_hashes.json)
  - Flag changed LPs
  - Store in ad_metadata.lp_changed

No external HTTP requests are made - only local cached HTML is checked.

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/detect_lp_changes.py
"""

import os
import sys
import json
import hashlib
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media_cache")
)
LP_HTML_DIR = os.path.join(CACHE_DIR, "lp_html")

DATA_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
)
HASH_PATH = os.path.join(DATA_DIR, "lp_hashes.json")


def _load_previous_hashes() -> dict[str, str]:
    """Load previous LP hashes from storage."""
    if not os.path.exists(HASH_PATH):
        return {}
    try:
        with open(HASH_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("hashes", {})
    except (json.JSONDecodeError, OSError):
        return {}


def _hash_file(path: str) -> str | None:
    """Compute SHA-256 hash of a file."""
    try:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            while True:
                chunk = f.read(65536)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
    except OSError:
        return None


def main():
    os.makedirs(DATA_DIR, exist_ok=True)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print("Loaded %d ads" % len(ads))

        # Filter ads with destination URLs (LP URLs)
        ads_with_lp = [ad for ad in ads if ad.destination_url]
        print("Ads with LP URL: %d" % len(ads_with_lp))

        previous_hashes = _load_previous_hashes()
        print("Previous hashes loaded: %d" % len(previous_hashes))

        now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        new_hashes: dict[str, str] = {}

        checked = 0
        changed = 0
        unchanged = 0
        no_cache = 0

        for ad in ads_with_lp:
            ad_id_str = str(ad.id)
            html_path = os.path.join(LP_HTML_DIR, "%d.html" % ad.id)

            meta = ad.ad_metadata or {}

            if not os.path.exists(html_path):
                no_cache += 1
                # No cached HTML - can't check
                meta["lp_changed"] = {
                    "last_check": now_str,
                    "changed": False,
                    "status": "no_cache",
                }
                ad.ad_metadata = meta
                flag_modified(ad, "ad_metadata")
                continue

            current_hash = _hash_file(html_path)
            if not current_hash:
                no_cache += 1
                continue

            checked += 1
            new_hashes[ad_id_str] = current_hash

            prev_hash = previous_hashes.get(ad_id_str)
            if prev_hash and prev_hash != current_hash:
                changed += 1
                meta["lp_changed"] = {
                    "last_check": now_str,
                    "changed": True,
                    "previous_hash": prev_hash[:16],
                    "current_hash": current_hash[:16],
                }
            else:
                unchanged += 1
                meta["lp_changed"] = {
                    "last_check": now_str,
                    "changed": False,
                    "status": "unchanged" if prev_hash else "first_check",
                }

            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

        session.commit()

        # Save new hashes
        hash_data = {
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "total_entries": len(new_hashes),
            "hashes": new_hashes,
        }
        with open(HASH_PATH, "w", encoding="utf-8") as f:
            json.dump(hash_data, f, indent=2)

        print("\n=== LP Change Detection Summary ===")
        print("Checked %d LPs, %d have changed since last check" % (checked, changed))
        print("Unchanged: %d" % unchanged)
        print("No cached HTML: %d" % no_cache)
        print("Hash file saved: %s" % HASH_PATH)

    except Exception as e:
        session.rollback()
        print("ERROR: %s" % str(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
