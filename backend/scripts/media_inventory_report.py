"""Media inventory report: per-genre coverage, cache size, missing ads, final cache rate.

Generates a comprehensive report of the media cache status for all ads:
  - Per-genre media coverage table
  - Total cache size (MB)
  - Ads with no media at all
  - Final cache rate (thumbnail / image / video)

Run from the backend directory:
    cd backend
    python scripts/media_inventory_report.py
"""

import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# ── Config ────────────────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")
VIDEO_DIR = os.path.join(CACHE_DIR, "videos")
REFERENCE_DIR = os.path.join(CACHE_DIR, "reference")
SCENARIO_THUMB_DIR = os.path.join(CACHE_DIR, "scenario_thumbnails")
CONFIG_PATH = os.path.join(BASE_DIR, "config", "genre_crawl_keywords.json")


def _dir_size_bytes(dirpath: str) -> int:
    """Calculate total size of all files in a directory (non-recursive)."""
    total = 0
    if os.path.isdir(dirpath):
        for fname in os.listdir(dirpath):
            fpath = os.path.join(dirpath, fname)
            if os.path.isfile(fpath):
                total += os.path.getsize(fpath)
    return total


def _dir_size_recursive(dirpath: str) -> int:
    """Calculate total size of all files in a directory tree."""
    total = 0
    if os.path.isdir(dirpath):
        for root, dirs, files in os.walk(dirpath):
            for fname in files:
                fpath = os.path.join(root, fname)
                try:
                    total += os.path.getsize(fpath)
                except OSError:
                    pass
    return total


def _count_files(dirpath: str, extensions: tuple[str, ...] = (".jpg",)) -> int:
    """Count files with given extensions in a directory."""
    if not os.path.isdir(dirpath):
        return 0
    return sum(1 for f in os.listdir(dirpath) if any(f.endswith(ext) for ext in extensions))


def _cached_ad_ids(dirpath: str, extensions: tuple[str, ...] = (".jpg",)) -> set[int]:
    """Return set of ad IDs that have cached files."""
    result = set()
    if not os.path.isdir(dirpath):
        return result
    for fname in os.listdir(dirpath):
        for ext in extensions:
            if fname.endswith(ext):
                try:
                    ad_id = int(fname.replace(ext, ""))
                    result.add(ad_id)
                except ValueError:
                    pass
    return result


def load_genres() -> dict:
    """Load genre definitions from config."""
    if os.path.exists(CONFIG_PATH):
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get("genres", {})
    return {}


def main():
    print("=" * 76)
    print("  MEDIA INVENTORY REPORT")
    print("=" * 76)
    print()

    session = SyncSessionLocal()
    try:
        all_ads = session.query(Ad).order_by(Ad.id).all()
        total_ads = len(all_ads)

        # Build lookup structures
        ad_ids = {ad.id for ad in all_ads}

        # Cached file sets
        thumb_ids = _cached_ad_ids(THUMB_DIR, (".jpg",))
        img_ids = _cached_ad_ids(IMAGE_DIR, (".jpg",))
        video_ids = _cached_ad_ids(VIDEO_DIR, (".mp4", ".webm", ".mov"))

        # Intersect with actual ad IDs (ignore orphans)
        thumb_cached = thumb_ids & ad_ids
        img_cached = img_ids & ad_ids
        video_cached = video_ids & ad_ids

        # Any media at all
        any_media = thumb_cached | img_cached | video_cached
        no_media_ids = ad_ids - any_media

        # ── Section 1: Per-genre media coverage ──────────────────
        genres = load_genres()
        genre_keys = sorted(genres.keys())

        # Group ads by genre
        genre_map: dict[str, list[int]] = {g: [] for g in genre_keys}
        unclassified_ids: list[int] = []

        for ad in all_ads:
            meta = ad.ad_metadata or {}
            fg_en = meta.get("fine_genre_en", "")
            if fg_en in genre_map:
                genre_map[fg_en].append(ad.id)
            else:
                unclassified_ids.append(ad.id)

        print("  1. PER-GENRE MEDIA COVERAGE")
        print("  " + "-" * 74)
        header = "  {:<30s} {:>5s} {:>8s} {:>8s} {:>8s} {:>8s}".format(
            "Genre", "Ads", "Thumb", "Image", "Video", "Any%"
        )
        print(header)
        print("  " + "-" * 74)

        for gk in genre_keys:
            g_ad_ids = set(genre_map[gk])
            g_total = len(g_ad_ids)
            if g_total == 0:
                print("  {:<30s} {:>5d} {:>8s} {:>8s} {:>8s} {:>8s}".format(
                    gk[:30], 0, "-", "-", "-", "-"
                ))
                continue

            g_thumb = len(g_ad_ids & thumb_cached)
            g_img = len(g_ad_ids & img_cached)
            g_video = len(g_ad_ids & video_cached)
            g_any = len(g_ad_ids & any_media)
            g_pct = g_any * 100 / g_total if g_total > 0 else 0

            print("  {:<30s} {:>5d} {:>8d} {:>8d} {:>8d} {:>7.1f}%".format(
                gk[:30], g_total, g_thumb, g_img, g_video, g_pct
            ))

        # Unclassified row
        if unclassified_ids:
            u_ids = set(unclassified_ids)
            u_total = len(u_ids)
            u_thumb = len(u_ids & thumb_cached)
            u_img = len(u_ids & img_cached)
            u_video = len(u_ids & video_cached)
            u_any = len(u_ids & any_media)
            u_pct = u_any * 100 / u_total if u_total > 0 else 0
            print("  " + "-" * 74)
            print("  {:<30s} {:>5d} {:>8d} {:>8d} {:>8d} {:>7.1f}%".format(
                "(unclassified)", u_total, u_thumb, u_img, u_video, u_pct
            ))

        print("  " + "-" * 74)

        # Total row
        t_pct = len(any_media) * 100 / total_ads if total_ads > 0 else 0
        print("  {:<30s} {:>5d} {:>8d} {:>8d} {:>8d} {:>7.1f}%".format(
            "TOTAL", total_ads, len(thumb_cached), len(img_cached),
            len(video_cached), t_pct
        ))
        print()

        # ── Section 2: Total cache size ──────────────────────────
        print("  2. CACHE SIZE")
        print("  " + "-" * 74)

        thumb_size = _dir_size_bytes(THUMB_DIR)
        img_size = _dir_size_bytes(IMAGE_DIR)
        video_size = _dir_size_bytes(VIDEO_DIR)
        ref_size = _dir_size_recursive(REFERENCE_DIR)
        scenario_size = _dir_size_bytes(SCENARIO_THUMB_DIR)
        total_cache = _dir_size_recursive(CACHE_DIR)

        mb = 1024 * 1024
        print("  {:<30s} {:>10.2f} MB".format("Thumbnails", thumb_size / mb))
        print("  {:<30s} {:>10.2f} MB".format("Images", img_size / mb))
        print("  {:<30s} {:>10.2f} MB".format("Videos", video_size / mb))
        print("  {:<30s} {:>10.2f} MB".format("Reference media", ref_size / mb))
        print("  {:<30s} {:>10.2f} MB".format("Scenario thumbnails", scenario_size / mb))
        print("  " + "-" * 44)
        print("  {:<30s} {:>10.2f} MB".format("TOTAL CACHE", total_cache / mb))
        print()

        # ── Section 3: Ads with no media ─────────────────────────
        print("  3. ADS WITH NO MEDIA")
        print("  " + "-" * 74)
        print("  Count: %d / %d" % (len(no_media_ids), total_ads))

        if no_media_ids:
            sorted_missing = sorted(no_media_ids)
            # Show up to 50 IDs
            display = sorted_missing[:50]
            print("  IDs: %s" % ", ".join(str(i) for i in display))
            if len(sorted_missing) > 50:
                print("  ... and %d more" % (len(sorted_missing) - 50))

            # Show details for missing ads (reasons)
            missing_ads_data = [ad for ad in all_ads if ad.id in no_media_ids]
            no_url_count = 0
            has_url_but_no_cache = 0
            for ad in missing_ads_data:
                if not ad.thumbnail_url and not ad.image_url:
                    no_url_count += 1
                else:
                    has_url_but_no_cache += 1
            print()
            print("  Breakdown:")
            print("    No thumbnail_url and no image_url: %d" % no_url_count)
            print("    Has URL but download failed:       %d" % has_url_but_no_cache)
        else:
            print("  All ads have at least one cached media file.")
        print()

        # ── Section 4: Final cache rate ──────────────────────────
        print("  4. FINAL CACHE RATES")
        print("  " + "-" * 74)

        thumb_rate = len(thumb_cached) * 100 / total_ads if total_ads > 0 else 0
        img_rate = len(img_cached) * 100 / total_ads if total_ads > 0 else 0
        video_rate = len(video_cached) * 100 / total_ads if total_ads > 0 else 0
        any_rate = len(any_media) * 100 / total_ads if total_ads > 0 else 0

        print("  Total ads:              %d" % total_ads)
        print("  Thumbnails cached:      %d / %d (%.1f%%)" % (
            len(thumb_cached), total_ads, thumb_rate
        ))
        print("  Images cached:          %d / %d (%.1f%%)" % (
            len(img_cached), total_ads, img_rate
        ))
        print("  Videos cached:          %d / %d (%.1f%%)" % (
            len(video_cached), total_ads, video_rate
        ))
        print("  Any media cached:       %d / %d (%.1f%%)" % (
            len(any_media), total_ads, any_rate
        ))
        print()

        # Reference media and scenario thumbnails
        ref_genres = 0
        ref_index_path = os.path.join(REFERENCE_DIR, "reference_media.json")
        if os.path.exists(ref_index_path):
            try:
                with open(ref_index_path, "r", encoding="utf-8") as f:
                    ref_data = json.load(f)
                ref_genres = len(ref_data.get("genres", {}))
            except Exception:
                pass

        scenario_thumbs = _count_files(SCENARIO_THUMB_DIR, (".svg",))

        print("  Reference media genres: %d" % ref_genres)
        print("  Scenario thumbnails:    %d" % scenario_thumbs)
        print()

        # Frontend cache hit prediction
        print("  5. FRONTEND CACHE HIT PREDICTION")
        print("  " + "-" * 74)
        # For the frontend, thumbnail is the main display; image is detail view
        # Cache hit = ad has at least a thumbnail OR image
        thumb_or_img = thumb_cached | img_cached
        hit_rate = len(thumb_or_img) * 100 / total_ads if total_ads > 0 else 0
        print("  Thumbnail or image available: %d / %d (%.1f%%)" % (
            len(thumb_or_img), total_ads, hit_rate
        ))
        print("  Expected frontend cache hit:  %.1f%%" % hit_rate)
        print("  Expected placeholder SVGs:    %d ads" % (total_ads - len(thumb_or_img)))
        print()

        # Status assessment
        print("=" * 76)
        if any_rate >= 90:
            print("  STATUS: EXCELLENT - media coverage is above 90%%")
        elif any_rate >= 80:
            print("  STATUS: GOOD - media coverage is above 80%%")
        elif any_rate >= 60:
            print("  STATUS: FAIR - consider running aggressive_media_recovery.py")
        else:
            print("  STATUS: NEEDS WORK - run auto_media_cache.py + aggressive_media_recovery.py")
        print("=" * 76)

    except Exception as e:
        print("FATAL ERROR: %s" % str(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
