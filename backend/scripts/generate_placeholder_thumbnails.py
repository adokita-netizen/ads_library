#!/usr/bin/env python3
"""Generate genre-based placeholder SVG thumbnails for ads without thumbnails.

For each ad that has no thumbnail_url, this script generates a simple,
visually distinctive SVG placeholder based on the ad's category/genre.
Placeholders are saved to backend/static/placeholders/ and the ad's
thumbnail_url is updated to point to the local file.

Usage:
    cd backend
    python -u scripts/generate_placeholder_thumbnails.py
    python -u scripts/generate_placeholder_thumbnails.py --dry-run
"""

import sys
import io
import os
import argparse
from datetime import datetime

# Windows cp932 compatibility
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLACEHOLDER_DIR = os.path.join(BASE_DIR, "static", "placeholders")

# Genre-based placeholder config: (background_color, icon_emoji_substitute, label)
# Since SVG text handles Unicode, we use simple geometric icons via SVG paths
# and readable category labels.
GENRE_PLACEHOLDERS = {
    "ec_d2c": {
        "bg": "#4A90D9",
        "accent": "#2C5F8A",
        "icon": "cart",
        "label": "EC / D2C",
    },
    "app": {
        "bg": "#7B68EE",
        "accent": "#5A4CBE",
        "icon": "phone",
        "label": "App",
    },
    "finance": {
        "bg": "#2ECC71",
        "accent": "#1E8C4E",
        "icon": "chart",
        "label": "Finance",
    },
    "education": {
        "bg": "#E67E22",
        "accent": "#A85C18",
        "icon": "book",
        "label": "Education",
    },
    "beauty": {
        "bg": "#E91E8C",
        "accent": "#B0156B",
        "icon": "star",
        "label": "Beauty",
    },
    "food": {
        "bg": "#F39C12",
        "accent": "#C87F0A",
        "icon": "utensils",
        "label": "Food",
    },
    "gaming": {
        "bg": "#9B59B6",
        "accent": "#7D3E98",
        "icon": "gamepad",
        "label": "Gaming",
    },
    "health": {
        "bg": "#1ABC9C",
        "accent": "#148F77",
        "icon": "heart",
        "label": "Health",
    },
    "technology": {
        "bg": "#34495E",
        "accent": "#1C2833",
        "icon": "gear",
        "label": "Technology",
    },
    "real_estate": {
        "bg": "#8B6914",
        "accent": "#6B5010",
        "icon": "house",
        "label": "Real Estate",
    },
    "travel": {
        "bg": "#3498DB",
        "accent": "#2473A6",
        "icon": "plane",
        "label": "Travel",
    },
    "other": {
        "bg": "#95A5A6",
        "accent": "#707B7C",
        "icon": "default",
        "label": "Other",
    },
}

# SVG icon paths (simple geometric shapes)
SVG_ICONS = {
    "cart": (
        '<circle cx="155" cy="195" r="8" fill="white" opacity="0.9"/>'
        '<circle cx="185" cy="195" r="8" fill="white" opacity="0.9"/>'
        '<path d="M130 120 L140 120 L160 175 L190 175 L195 140 L148 140" '
        'stroke="white" stroke-width="4" fill="none" opacity="0.9"/>'
    ),
    "phone": (
        '<rect x="150" y="110" width="40" height="70" rx="6" '
        'stroke="white" stroke-width="3" fill="none" opacity="0.9"/>'
        '<circle cx="170" cy="170" r="4" fill="white" opacity="0.9"/>'
    ),
    "chart": (
        '<rect x="140" y="160" width="15" height="30" fill="white" opacity="0.9"/>'
        '<rect x="160" y="140" width="15" height="50" fill="white" opacity="0.9"/>'
        '<rect x="180" y="120" width="15" height="70" fill="white" opacity="0.9"/>'
        '<line x1="130" y1="190" x2="205" y2="190" stroke="white" stroke-width="2" opacity="0.9"/>'
    ),
    "book": (
        '<path d="M145 120 L145 180 L170 170 L195 180 L195 120 L170 130 Z" '
        'stroke="white" stroke-width="3" fill="none" opacity="0.9"/>'
        '<line x1="170" y1="130" x2="170" y2="170" stroke="white" stroke-width="2" opacity="0.9"/>'
    ),
    "star": (
        '<polygon points="170,115 178,145 210,145 184,163 193,193 170,175 147,193 156,163 130,145 162,145" '
        'fill="white" opacity="0.9"/>'
    ),
    "utensils": (
        '<line x1="155" y1="120" x2="155" y2="180" stroke="white" stroke-width="4" stroke-linecap="round" opacity="0.9"/>'
        '<line x1="155" y1="120" x2="145" y2="140" stroke="white" stroke-width="3" stroke-linecap="round" opacity="0.9"/>'
        '<line x1="155" y1="120" x2="165" y2="140" stroke="white" stroke-width="3" stroke-linecap="round" opacity="0.9"/>'
        '<path d="M180 120 Q190 150 180 180" stroke="white" stroke-width="4" fill="none" stroke-linecap="round" opacity="0.9"/>'
    ),
    "gamepad": (
        '<rect x="140" y="135" width="60" height="35" rx="10" '
        'stroke="white" stroke-width="3" fill="none" opacity="0.9"/>'
        '<circle cx="157" cy="152" r="4" fill="white" opacity="0.9"/>'
        '<circle cx="183" cy="152" r="4" fill="white" opacity="0.9"/>'
    ),
    "heart": (
        '<path d="M170 180 L145 155 Q130 135 150 125 Q170 120 170 145 '
        'Q170 120 190 125 Q210 135 195 155 Z" '
        'fill="white" opacity="0.9"/>'
    ),
    "gear": (
        '<circle cx="170" cy="155" r="15" stroke="white" stroke-width="3" fill="none" opacity="0.9"/>'
        '<circle cx="170" cy="155" r="6" fill="white" opacity="0.9"/>'
        '<line x1="170" y1="130" x2="170" y2="137" stroke="white" stroke-width="4" opacity="0.9"/>'
        '<line x1="170" y1="173" x2="170" y2="180" stroke="white" stroke-width="4" opacity="0.9"/>'
        '<line x1="145" y1="155" x2="152" y2="155" stroke="white" stroke-width="4" opacity="0.9"/>'
        '<line x1="188" y1="155" x2="195" y2="155" stroke="white" stroke-width="4" opacity="0.9"/>'
    ),
    "house": (
        '<polygon points="170,115 135,150 205,150" '
        'stroke="white" stroke-width="3" fill="none" opacity="0.9"/>'
        '<rect x="145" y="150" width="50" height="35" '
        'stroke="white" stroke-width="3" fill="none" opacity="0.9"/>'
        '<rect x="160" y="162" width="20" height="23" '
        'stroke="white" stroke-width="2" fill="none" opacity="0.9"/>'
    ),
    "plane": (
        '<path d="M170 120 L185 155 L210 160 L185 165 L170 195 L155 165 L130 160 L155 155 Z" '
        'fill="white" opacity="0.9"/>'
    ),
    "default": (
        '<rect x="145" y="130" width="50" height="45" rx="5" '
        'stroke="white" stroke-width="3" fill="none" opacity="0.9"/>'
        '<circle cx="160" cy="148" r="6" fill="white" opacity="0.9"/>'
        '<polygon points="148,170 170,155 192,170" fill="white" opacity="0.6"/>'
    ),
}


def generate_placeholder_svg(genre_key: str, ad_id: int = 0) -> str:
    """Generate an SVG placeholder image for a given genre.

    Returns the SVG content as a string.
    """
    config = GENRE_PLACEHOLDERS.get(genre_key, GENRE_PLACEHOLDERS["other"])
    icon_key = config["icon"]
    icon_svg = SVG_ICONS.get(icon_key, SVG_ICONS["default"])

    svg = f"""<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 340 300" width="340" height="300">
  <defs>
    <linearGradient id="bg_{ad_id}" x1="0%" y1="0%" x2="100%" y2="100%">
      <stop offset="0%" style="stop-color:{config['bg']};stop-opacity:1"/>
      <stop offset="100%" style="stop-color:{config['accent']};stop-opacity:1"/>
    </linearGradient>
  </defs>

  <!-- Background -->
  <rect width="340" height="300" fill="url(#bg_{ad_id})" rx="8"/>

  <!-- Decorative circles -->
  <circle cx="50" cy="50" r="80" fill="white" opacity="0.05"/>
  <circle cx="300" cy="260" r="60" fill="white" opacity="0.05"/>

  <!-- Icon -->
  {icon_svg}

  <!-- Label -->
  <text x="170" y="230" text-anchor="middle" fill="white" font-family="Arial, sans-serif"
        font-size="16" font-weight="bold" opacity="0.9">{config['label']}</text>

  <!-- "No Image" subtitle -->
  <text x="170" y="255" text-anchor="middle" fill="white" font-family="Arial, sans-serif"
        font-size="11" opacity="0.6">No Preview Available</text>
</svg>"""

    return svg


def generate_genre_placeholders():
    """Generate one placeholder SVG file per genre and save to disk."""
    os.makedirs(PLACEHOLDER_DIR, exist_ok=True)

    generated = []
    for genre_key in GENRE_PLACEHOLDERS:
        svg_content = generate_placeholder_svg(genre_key, ad_id=0)
        filename = f"placeholder_{genre_key}.svg"
        filepath = os.path.join(PLACEHOLDER_DIR, filename)

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(svg_content)

        generated.append((genre_key, filepath))
        print(f"  Generated: {filename}")

    return generated


def assign_placeholders_to_ads(dry_run: bool = False) -> dict:
    """Find ads without thumbnails and assign genre-based placeholders.

    Returns stats dict.
    """
    from app.core.database import SyncSessionLocal
    from app.models.ad import Ad

    session = SyncSessionLocal()
    stats = {
        "total_ads": 0,
        "missing_thumbnail": 0,
        "assigned": 0,
        "by_genre": {},
    }

    try:
        ads = session.query(Ad).order_by(Ad.id).all()
        stats["total_ads"] = len(ads)

        # Find ads without thumbnail_url
        no_thumb_ads = [a for a in ads if not a.thumbnail_url]
        stats["missing_thumbnail"] = len(no_thumb_ads)

        print(f"  Total ads:          {stats['total_ads']}")
        print(f"  Missing thumbnail:  {stats['missing_thumbnail']}")
        print()

        if not no_thumb_ads:
            print("  All ads have thumbnails. Nothing to do.")
            return stats

        for ad in no_thumb_ads:
            # Determine genre from category or metadata
            genre_key = "other"

            # Check category enum
            if ad.category:
                cat_val = ad.category.value if hasattr(ad.category, "value") else str(ad.category)
                if cat_val in GENRE_PLACEHOLDERS:
                    genre_key = cat_val

            # Check metadata for jp_genre_key or fine_genre_en
            if genre_key == "other" and ad.ad_metadata:
                meta = ad.ad_metadata or {}
                for meta_key in ("jp_genre_key", "fine_genre_en"):
                    meta_genre = meta.get(meta_key, "")
                    if meta_genre in GENRE_PLACEHOLDERS:
                        genre_key = meta_genre
                        break

            # Build the placeholder path (relative to static serving root)
            placeholder_path = f"/static/placeholders/placeholder_{genre_key}.svg"

            if not dry_run:
                ad.thumbnail_url = placeholder_path
                # Tag in metadata
                meta = dict(ad.ad_metadata or {})
                meta["placeholder_thumbnail"] = True
                meta["placeholder_genre"] = genre_key
                ad.ad_metadata = meta
                from sqlalchemy.orm.attributes import flag_modified
                flag_modified(ad, "ad_metadata")

            stats["assigned"] += 1
            stats["by_genre"][genre_key] = stats["by_genre"].get(genre_key, 0) + 1

        if not dry_run:
            session.commit()
            print(f"  Assigned placeholders: {stats['assigned']}")
        else:
            print(f"  [DRY RUN] Would assign placeholders: {stats['assigned']}")

        # Print breakdown by genre
        if stats["by_genre"]:
            print()
            print("  Breakdown by genre:")
            for gk, count in sorted(stats["by_genre"].items(), key=lambda x: -x[1]):
                print(f"    {gk:20s}  {count}")

    except Exception as e:
        if not dry_run:
            session.rollback()
        print(f"  FATAL ERROR: {e}")
        raise
    finally:
        session.close()

    return stats


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate genre-based placeholder thumbnails"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Only report what would be done, do not modify DB",
    )
    args = parser.parse_args()

    print()
    print("=" * 70)
    print("  PLACEHOLDER THUMBNAIL GENERATOR")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)
    print()

    # Phase 1: Generate SVG files
    print("Phase 1: Generate placeholder SVG files")
    print("-" * 50)
    generated = generate_genre_placeholders()
    print(f"  Total generated: {len(generated)} SVG files")
    print(f"  Output directory: {PLACEHOLDER_DIR}")
    print()

    # Phase 2: Assign to ads
    print("Phase 2: Assign placeholders to ads without thumbnails")
    print("-" * 50)
    stats = assign_placeholders_to_ads(dry_run=args.dry_run)

    # Summary
    print()
    print("=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  SVG files generated:       {len(generated)}")
    print(f"  Ads without thumbnails:    {stats['missing_thumbnail']}")
    print(f"  Placeholders assigned:     {stats['assigned']}")
    if args.dry_run:
        print("  Mode: DRY RUN (no changes made)")
    print("=" * 70)
    print()


if __name__ == "__main__":
    main()
