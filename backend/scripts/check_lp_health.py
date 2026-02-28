"""
Check LP (Landing Page) health for all ads with destination_url.

Sends HEAD requests to each destination_url and records the HTTP status
in ad_metadata as lp_status and lp_checked_at.

Run: cd C:/Users/ishit/ads_library/backend && python scripts/check_lp_health.py
"""

import sys
import os
import time

# Ensure the backend package is importable
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timezone

import requests
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import sync_session_scope
from app.models.ad import Ad


# Request timeout in seconds
REQUEST_TIMEOUT = 10
# Delay between requests in seconds (rate limiting)
REQUEST_DELAY = 0.5
# User-Agent header
USER_AGENT = "AdsLibrary-LPHealthChecker/1.0"


def check_url_health(url: str) -> dict:
    """Send HEAD request to a URL and return status info."""
    try:
        resp = requests.head(
            url,
            timeout=REQUEST_TIMEOUT,
            allow_redirects=True,
            headers={"User-Agent": USER_AGENT},
        )
        return {
            "status_code": resp.status_code,
            "lp_status": str(resp.status_code),
            "final_url": resp.url if resp.url != url else None,
            "redirect_count": len(resp.history),
        }
    except requests.exceptions.Timeout:
        return {
            "status_code": None,
            "lp_status": "timeout",
            "final_url": None,
            "redirect_count": 0,
        }
    except requests.exceptions.ConnectionError:
        return {
            "status_code": None,
            "lp_status": "connection_error",
            "final_url": None,
            "redirect_count": 0,
        }
    except requests.exceptions.TooManyRedirects:
        return {
            "status_code": None,
            "lp_status": "too_many_redirects",
            "final_url": None,
            "redirect_count": 0,
        }
    except requests.exceptions.SSLError:
        return {
            "status_code": None,
            "lp_status": "ssl_error",
            "final_url": None,
            "redirect_count": 0,
        }
    except Exception as e:
        return {
            "status_code": None,
            "lp_status": "error",
            "final_url": None,
            "redirect_count": 0,
            "error_detail": str(e)[:200],
        }


def main():
    print("=" * 60)
    print("LP Health Check Script")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    with sync_session_scope() as session:
        # Get all ads with a destination_url
        ads = (
            session.query(Ad)
            .filter(Ad.destination_url.isnot(None))
            .filter(Ad.destination_url != "")
            .all()
        )
        total = len(ads)
        print(f"\nAds with destination_url: {total}")

        if total == 0:
            print("No ads with destination_url found. Exiting.")
            return

        # Counters
        status_counts = {}
        checked = 0
        errors = 0

        for i, ad in enumerate(ads, 1):
            url = ad.destination_url.strip()
            if not url:
                continue

            # Add scheme if missing
            if not url.startswith("http://") and not url.startswith("https://"):
                url = "https://" + url

            result = check_url_health(url)
            lp_status = result["lp_status"]
            now_iso = datetime.now(timezone.utc).isoformat()

            # Update ad_metadata using flag_modified pattern
            meta = dict(ad.ad_metadata or {})
            meta["lp_status"] = lp_status
            meta["lp_checked_at"] = now_iso
            if result.get("final_url"):
                meta["lp_final_url"] = result["final_url"]
            if result.get("error_detail"):
                meta["lp_error_detail"] = result["error_detail"]
            ad.ad_metadata = meta
            flag_modified(ad, "ad_metadata")

            # Track counts
            status_counts[lp_status] = status_counts.get(lp_status, 0) + 1
            checked += 1

            if lp_status not in ("200", "301", "302", "303"):
                errors += 1

            # Progress logging every 50 ads
            if i % 50 == 0 or i == total:
                print(f"  Progress: {i}/{total} checked ({checked} done, {errors} issues)")

            # Commit every 100 ads to avoid large transactions
            if i % 100 == 0:
                session.commit()

            # Rate limiting
            time.sleep(REQUEST_DELAY)

        # Final commit
        session.commit()

        # Print summary
        print("\n" + "=" * 60)
        print("LP Health Check Summary")
        print("=" * 60)
        print(f"Total checked: {checked}")
        print(f"Issues found:  {errors}")
        print("\nStatus distribution:")
        for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
            print(f"  {status}: {count}")
        print("\nDone.")


if __name__ == "__main__":
    main()
