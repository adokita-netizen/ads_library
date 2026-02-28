#!/usr/bin/env python3
"""Generate smart SVG placeholders for ads missing thumbnails.

For ads without cached thumbnails, generates informative SVG placeholders:
  - Include ad title text (truncated)
  - Genre-specific color scheme
  - Hit score badge if available
  - Advertiser name
  - Platform icon

Stores generated SVGs in media_cache/placeholders/

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/generate_smart_placeholders.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media_cache")
)
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
PLACEHOLDER_DIR = os.path.join(CACHE_DIR, "placeholders")

# Genre-specific color schemes (bg, accent, text)
GENRE_COLORS = {
    "skincare": ("#FFF0F5", "#E91E63", "#880E4F"),
    "supplement": ("#F1F8E9", "#8BC34A", "#33691E"),
    "diet": ("#E8F5E9", "#4CAF50", "#1B5E20"),
    "cosmetics": ("#FCE4EC", "#F06292", "#AD1457"),
    "hair_care": ("#E3F2FD", "#42A5F5", "#0D47A1"),
    "medical_weight_loss": ("#E0F7FA", "#00BCD4", "#006064"),
    "dental": ("#E8EAF6", "#5C6BC0", "#1A237E"),
    "mens_cosmetics": ("#ECEFF1", "#607D8B", "#263238"),
    "fitness": ("#FFF3E0", "#FF9800", "#E65100"),
    "health_food": ("#F9FBE7", "#CDDC39", "#827717"),
    "anti_aging": ("#F3E5F5", "#AB47BC", "#4A148C"),
    "whitening": ("#FFFDE7", "#FFEE58", "#F57F17"),
    "default": ("#F5F5F5", "#9E9E9E", "#424242"),
}

# Platform icons (simple text-based)
PLATFORM_ICONS = {
    "facebook": "fb",
    "instagram": "IG",
    "youtube": "YT",
    "tiktok": "TT",
    "x_twitter": "X",
    "line": "LN",
    "yahoo": "Y!",
    "google_ads": "G",
    "other": "AD",
}


def _escape_svg(text: str) -> str:
    """Escape text for SVG content."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#x27;")
    )


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max length with ellipsis."""
    if not text:
        return ""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _generate_svg(ad: Ad, genre: str) -> str:
    """Generate a smart SVG placeholder for an ad."""
    meta = ad.ad_metadata or {}

    # Get colors for genre
    colors = GENRE_COLORS.get(genre, GENRE_COLORS["default"])
    bg_color, accent_color, text_color = colors

    # Get info
    title = _escape_svg(_truncate(ad.title or "Untitled Ad", 35))
    advertiser = _escape_svg(_truncate(ad.advertiser_name or "", 30))
    platform = ad.platform.value if hasattr(ad.platform, "value") else str(ad.platform)
    platform_icon = PLATFORM_ICONS.get(platform, "AD")

    # Hit score
    try:
        hit_score = float(meta.get("latest_hit_score", 0) or 0)
    except (ValueError, TypeError):
        hit_score = 0

    genre_label = _escape_svg(genre.replace("_", " ").title()[:20])

    # Build SVG
    svg_parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">',
        '<defs>',
        '  <linearGradient id="bg_%d" x1="0" y1="0" x2="0" y2="1">' % ad.id,
        '    <stop offset="0%%" stop-color="%s"/>' % bg_color,
        '    <stop offset="100%%" stop-color="#ffffff"/>',
        '  </linearGradient>',
        '</defs>',
        # Background
        '<rect width="400" height="300" rx="8" fill="url(#bg_%d)"/>' % ad.id,
        # Top accent bar
        '<rect width="400" height="4" fill="%s"/>' % accent_color,
        # Platform badge (top-left)
        '<rect x="12" y="12" width="36" height="24" rx="4" fill="%s"/>' % accent_color,
        '<text x="30" y="29" text-anchor="middle" font-family="Arial" font-size="11" '
        'font-weight="bold" fill="white">%s</text>' % platform_icon,
    ]

    # Hit score badge (top-right) if available
    if hit_score > 0:
        badge_color = (
            "#4CAF50" if hit_score >= 70 else
            "#FF9800" if hit_score >= 40 else
            "#F44336"
        )
        svg_parts.extend([
            '<rect x="340" y="12" width="48" height="24" rx="12" fill="%s"/>' % badge_color,
            '<text x="364" y="29" text-anchor="middle" font-family="Arial" font-size="11" '
            'font-weight="bold" fill="white">%.0f</text>' % hit_score,
        ])

    # Genre label (center-top area)
    svg_parts.extend([
        '<text x="200" y="70" text-anchor="middle" font-family="Arial" font-size="12" '
        'fill="%s" opacity="0.7">%s</text>' % (text_color, genre_label),
    ])

    # Large media icon (center)
    svg_parts.extend([
        '<rect x="160" y="90" width="80" height="60" rx="8" fill="none" '
        'stroke="%s" stroke-width="2" opacity="0.4"/>' % accent_color,
        '<polygon points="185,108 185,138 210,123" fill="%s" opacity="0.3"/>' % accent_color,
    ])

    # Title text (below center)
    svg_parts.extend([
        '<text x="200" y="185" text-anchor="middle" font-family="Arial" font-size="14" '
        'font-weight="600" fill="%s">%s</text>' % (text_color, title),
    ])

    # Advertiser name (bottom area)
    if advertiser:
        svg_parts.extend([
            '<text x="200" y="210" text-anchor="middle" font-family="Arial" font-size="11" '
            'fill="%s" opacity="0.6">%s</text>' % (text_color, advertiser),
        ])

    # Bottom bar with ad ID
    svg_parts.extend([
        '<rect x="0" y="274" width="400" height="26" fill="%s" opacity="0.1"/>' % accent_color,
        '<text x="200" y="291" text-anchor="middle" font-family="Arial" font-size="10" '
        'fill="%s" opacity="0.5">Ad #%d</text>' % (text_color, ad.id),
    ])

    svg_parts.append('</svg>')
    return '\n'.join(svg_parts)


def main():
    os.makedirs(PLACEHOLDER_DIR, exist_ok=True)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print("Loaded %d ads" % len(ads))

        generated = 0
        skipped = 0

        for ad in ads:
            # Check if thumbnail already exists
            thumb_path = os.path.join(THUMB_DIR, "%d.jpg" % ad.id)
            if os.path.exists(thumb_path):
                skipped += 1
                continue

            meta = ad.ad_metadata or {}
            genre = meta.get("fine_genre_en", "default")

            svg_content = _generate_svg(ad, genre)
            svg_path = os.path.join(PLACEHOLDER_DIR, "%d.svg" % ad.id)

            with open(svg_path, "w", encoding="utf-8") as f:
                f.write(svg_content)

            generated += 1

        print("\n=== Smart Placeholder Generation ===")
        print("Generated %d smart placeholders" % generated)
        print("Skipped %d (thumbnail exists)" % skipped)
        print("Output directory: %s" % PLACEHOLDER_DIR)

    except Exception as e:
        print("ERROR: %s" % str(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
