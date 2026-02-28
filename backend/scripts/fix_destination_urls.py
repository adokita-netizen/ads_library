"""Fix ads with NULL destination_url.

For each ad missing a destination_url, try extracting from (in priority order):
  a. ad_metadata["destination_url"]  -- may already be stored in JSON metadata
  b. ad_metadata["display_url"]      -- display URL, prepend https:// if needed
  c. ad_metadata["all_external_links"] -- array of external links from crawl
  d. ad_metadata["link_url"] or ad_metadata["website_url"]  -- Meta API fields
  e. Extract URLs from description text using regex

Facebook ads library snapshot URLs (facebook.com/ads/library) are NOT valid
destinations and are skipped.

Run from the backend directory:
    cd backend
    python scripts/fix_destination_urls.py
"""

import re
import sys

sys.path.insert(0, ".")

from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal
from app.models.ad import Ad


# ── URL helpers ────────────────────────────────────────────────────

# Pattern to extract URLs from text
_URL_RE = re.compile(r"https?://[^\s<>\"'\)\]]+", re.IGNORECASE)

# Domains to exclude as destination URLs (these are ad library / snapshot URLs)
_EXCLUDED_DOMAINS = [
    "facebook.com/ads/library",
    "www.facebook.com/ads/library",
    "adstransparency.google.com",
    "library.tiktok.com",
]


def _is_valid_destination(url: str | None) -> bool:
    """Check if a URL is a valid destination (not None, not empty, starts with http, not a snapshot URL)."""
    if not url or not isinstance(url, str):
        return False
    url = url.strip()
    if not url:
        return False
    if not url.startswith("http://") and not url.startswith("https://"):
        return False
    # Exclude ad library / snapshot URLs
    for domain in _EXCLUDED_DOMAINS:
        if domain in url.lower():
            return False
    return True


def _normalize_url(url: str) -> str:
    """Ensure URL starts with http:// or https://."""
    url = url.strip()
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"https://{url}"


def _extract_from_metadata(metadata: dict | None) -> str | None:
    """Try to extract destination URL from ad_metadata dict.

    Priority:
      1. destination_url
      2. display_url (normalize)
      3. all_external_links (first valid)
      4. link_url / website_url (Meta API fields)
    """
    if not metadata or not isinstance(metadata, dict):
        return None

    # 1. destination_url in metadata
    dest = metadata.get("destination_url")
    if dest and isinstance(dest, str):
        normalized = _normalize_url(dest)
        if _is_valid_destination(normalized):
            return normalized

    # 2. display_url
    display = metadata.get("display_url")
    if display and isinstance(display, str):
        normalized = _normalize_url(display)
        if _is_valid_destination(normalized):
            return normalized

    # 3. all_external_links
    links = metadata.get("all_external_links")
    if links and isinstance(links, list):
        for link in links:
            if link and isinstance(link, str):
                normalized = _normalize_url(link)
                if _is_valid_destination(normalized):
                    return normalized

    # 4. link_url / website_url (Meta API)
    for key in ("link_url", "website_url"):
        val = metadata.get(key)
        if val and isinstance(val, str):
            normalized = _normalize_url(val)
            if _is_valid_destination(normalized):
                return normalized

    return None


def _extract_from_description(description: str | None) -> str | None:
    """Try to extract a URL from the ad description text."""
    if not description or not isinstance(description, str):
        return None

    urls = _URL_RE.findall(description)
    for url in urls:
        # Clean trailing punctuation that might have been captured
        url = url.rstrip(".,;:!?)>]}")
        if _is_valid_destination(url):
            return url

    return None


def find_destination_url(ad: Ad) -> str | None:
    """Try all strategies to find a destination URL for an ad."""
    # Strategy 1-4: from metadata
    url = _extract_from_metadata(ad.ad_metadata)
    if url:
        return url

    # Strategy 5: from description text
    url = _extract_from_description(ad.description)
    if url:
        return url

    return None


def main():
    session = SyncSessionLocal()
    try:
        # Count before
        total_count = session.query(Ad).count()
        null_count_before = (
            session.query(Ad)
            .filter(Ad.destination_url == None)  # noqa: E711
            .count()
        )
        has_dest_count = total_count - null_count_before
        print(f"Total ads: {total_count}")
        print(f"Ads WITH destination_url: {has_dest_count}")
        print(f"Ads with NULL destination_url (before): {null_count_before}")
        print()

        if null_count_before == 0:
            print("No ads to fix. Exiting.")
            return

        # Fetch all ads with NULL destination_url
        ads = (
            session.query(Ad)
            .filter(Ad.destination_url == None)  # noqa: E711
            .all()
        )

        fixed = 0
        skipped = 0
        sources = {
            "metadata_destination_url": 0,
            "metadata_display_url": 0,
            "metadata_external_links": 0,
            "metadata_link_or_website_url": 0,
            "description_regex": 0,
            "not_found": 0,
        }

        for ad in ads:
            url = find_destination_url(ad)
            if url:
                ad.destination_url = url

                # Also update metadata to record the destination
                if ad.ad_metadata is None:
                    ad.ad_metadata = {}
                if not ad.ad_metadata.get("destination_url"):
                    ad.ad_metadata["destination_url"] = url
                    ad.ad_metadata["destination_type"] = "LP"
                    flag_modified(ad, "ad_metadata")

                fixed += 1

                # Track which source provided the URL
                meta = ad.ad_metadata or {}
                if meta.get("destination_url") == url and "destination_url" in (ad.ad_metadata or {}):
                    # Check what source matched (based on priority order)
                    orig_meta = ad.ad_metadata or {}
                    if _is_valid_destination(_normalize_url(str(orig_meta.get("destination_url", "")))):
                        sources["metadata_destination_url"] += 1
                    elif _is_valid_destination(_normalize_url(str(orig_meta.get("display_url", "")))):
                        sources["metadata_display_url"] += 1
                    elif orig_meta.get("all_external_links"):
                        sources["metadata_external_links"] += 1
                    elif orig_meta.get("link_url") or orig_meta.get("website_url"):
                        sources["metadata_link_or_website_url"] += 1
                    else:
                        sources["description_regex"] += 1
                else:
                    sources["description_regex"] += 1

                if fixed <= 30:
                    print(f"  [{ad.id}] {ad.platform.value:>10} -> {url[:80]}")
                elif fixed == 31:
                    print(f"  ... (showing first 30 of fixes)")
            else:
                skipped += 1
                sources["not_found"] += 1
                if skipped <= 10:
                    desc_preview = (ad.description or "")[:60].replace("\n", " ")
                    print(f"  [{ad.id}] SKIP ({ad.platform.value}) desc={repr(desc_preview)}")

        session.commit()

        print(f"\n--- Results ---")
        print(f"Fixed: {fixed}")
        print(f"Could not find URL: {skipped}")
        print(f"\nSource breakdown:")
        for source, count in sources.items():
            if count > 0:
                print(f"  {source}: {count}")

        # Verify
        null_count_after = (
            session.query(Ad)
            .filter(Ad.destination_url == None)  # noqa: E711
            .count()
        )
        print(f"\nAds with NULL destination_url (after): {null_count_after}")

        if null_count_after == 0:
            print("All ads now have destination URLs!")
        elif null_count_after < null_count_before:
            print(f"Reduced NULL destination_urls from {null_count_before} to {null_count_after} "
                  f"({null_count_before - null_count_after} fixed)")
        else:
            print(f"WARNING: {null_count_after} ads still have NULL destination_url.")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
