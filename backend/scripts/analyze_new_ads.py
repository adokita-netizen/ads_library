#!/usr/bin/env python3
"""Analyze creative elements for all unanalyzed ads.

Imports analyze_ad from analyze_creative_elements.py and processes ads
missing creative_analysis in ad_metadata.

Run:
    cd C:/Users/ishit/ads_library/backend
    set PYTHONIOENCODING=utf-8
    python scripts/analyze_new_ads.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from scripts.analyze_creative_elements import analyze_ad


# ── Main ─────────────────────────────────────────────────────────────────


def main():
    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        total = len(ads)
        print(f"[analyze_new_ads] Total ads: {total}")

        analyzed_new = 0
        validated = 0
        fixed = 0

        for ad in ads:
            meta = dict(ad.ad_metadata or {})
            ca = meta.get("creative_analysis")

            if not ca:
                # New: needs analysis
                result = analyze_ad(ad)
                if result:
                    meta["creative_analysis"] = result
                    ad.ad_metadata = meta
                    flag_modified(ad, "ad_metadata")
                    analyzed_new += 1
            else:
                # Validate existing: check for "none" values that could be better
                validated += 1
                text = f"{ad.title or ''} {ad.description or ''}"
                if not text.strip():
                    continue

                # Re-analyze and compare
                result = analyze_ad(ad)
                if not result:
                    continue

                needs_fix = False
                # Only update if new analysis has non-"none" values where old had "none"
                for field in ["hook_type", "cta_type", "offer_type", "emotion"]:
                    old_val = ca.get(field, "none")
                    new_val = result.get(field, "none")
                    if old_val == "none" and new_val != "none":
                        ca[field] = new_val
                        needs_fix = True

                if needs_fix:
                    meta["creative_analysis"] = ca
                    ad.ad_metadata = meta
                    flag_modified(ad, "ad_metadata")
                    fixed += 1

        session.commit()
        print(f"  Analyzed new: {analyzed_new}")
        print(f"  Validated existing: {validated}")
        print(f"  Fixed (improved from 'none'): {fixed}")

        # Summary
        remaining = sum(
            1 for a in session.query(Ad).all()
            if not (a.ad_metadata or {}).get("creative_analysis")
        )
        print(f"  Remaining without creative_analysis: {remaining}")

    finally:
        session.close()


if __name__ == "__main__":
    main()
