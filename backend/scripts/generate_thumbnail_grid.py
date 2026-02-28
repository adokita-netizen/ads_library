#!/usr/bin/env python3
"""Generate composite thumbnail grid images for each genre.

Creates 3x3 grids of top 9 ads per genre:
  - Each cell: 200x200px thumbnail
  - Genre label overlay
  - Hit rate badge
Uses Pillow if available, else generates SVG grids.

Output: media_cache/grids/

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/generate_thumbnail_grid.py
"""

import os
import sys
from datetime import datetime, timezone
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.core.database import SyncSessionLocal
from app.models.ad import Ad

CACHE_DIR = os.path.normpath(
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "media_cache")
)
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
GRID_DIR = os.path.join(CACHE_DIR, "grids")

CELL_SIZE = 200
GRID_COLS = 3
GRID_ROWS = 3
GRID_WIDTH = CELL_SIZE * GRID_COLS
GRID_HEIGHT = CELL_SIZE * GRID_ROWS + 40  # extra for header

GENRE_COLORS = {
    "skincare": "#E91E63",
    "supplement": "#8BC34A",
    "diet": "#4CAF50",
    "cosmetics": "#F06292",
    "hair_care": "#42A5F5",
    "medical_weight_loss": "#00BCD4",
    "dental": "#5C6BC0",
    "mens_cosmetics": "#607D8B",
    "fitness": "#FF9800",
    "health_food": "#CDDC39",
    "anti_aging": "#AB47BC",
    "whitening": "#FFEE58",
    "default": "#9E9E9E",
}


def _escape_svg(text: str) -> str:
    """Escape text for SVG."""
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _try_pillow_grid(genre: str, ad_entries: list[dict], color: str) -> bool:
    """Try to generate grid image using Pillow. Returns True if successful."""
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError:
        return False

    try:
        img = Image.new("RGB", (GRID_WIDTH, GRID_HEIGHT), "white")
        draw = ImageDraw.Draw(img)

        # Header
        draw.rectangle([0, 0, GRID_WIDTH, 40], fill=color)
        genre_label = genre.replace("_", " ").title()
        try:
            font = ImageFont.truetype("arial.ttf", 16)
            font_small = ImageFont.truetype("arial.ttf", 11)
        except OSError:
            font = ImageFont.load_default()
            font_small = font
        draw.text((10, 10), genre_label, fill="white", font=font)
        draw.text((GRID_WIDTH - 100, 14), "%d ads" % len(ad_entries), fill="white", font=font_small)

        # Grid cells
        for i, entry in enumerate(ad_entries[:9]):
            row = i // GRID_COLS
            col = i % GRID_COLS
            x = col * CELL_SIZE
            y = row * CELL_SIZE + 40

            thumb_path = entry.get("thumb_path", "")
            if thumb_path and os.path.exists(thumb_path):
                try:
                    thumb = Image.open(thumb_path).convert("RGB")
                    thumb = thumb.resize((CELL_SIZE, CELL_SIZE), Image.LANCZOS)
                    img.paste(thumb, (x, y))
                except Exception:
                    # Fill with placeholder color
                    draw.rectangle([x, y, x + CELL_SIZE, y + CELL_SIZE], fill="#f0f0f0")
                    draw.text((x + 60, y + 90), "No image", fill="#999", font=font_small)
            else:
                draw.rectangle([x, y, x + CELL_SIZE, y + CELL_SIZE], fill="#f0f0f0")
                draw.text((x + 60, y + 90), "No image", fill="#999", font=font_small)

            # Score badge
            score = entry.get("score", 0)
            if score > 0:
                badge_color = "#4CAF50" if score >= 70 else "#FF9800" if score >= 40 else "#F44336"
                draw.rectangle([x + CELL_SIZE - 40, y + 4, x + CELL_SIZE - 4, y + 22], fill=badge_color)
                draw.text((x + CELL_SIZE - 38, y + 6), "%.0f" % score, fill="white", font=font_small)

            # Cell border
            draw.rectangle([x, y, x + CELL_SIZE, y + CELL_SIZE], outline="#e0e0e0", width=1)

        output_path = os.path.join(GRID_DIR, "%s.jpg" % genre)
        img.save(output_path, "JPEG", quality=85)
        return True

    except Exception as e:
        print("  Pillow grid failed for %s: %s" % (genre, str(e)))
        return False


def _generate_svg_grid(genre: str, ad_entries: list[dict], color: str) -> str:
    """Generate an SVG grid as fallback."""
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" '
        'width="%d" height="%d" viewBox="0 0 %d %d">' % (
            GRID_WIDTH, GRID_HEIGHT, GRID_WIDTH, GRID_HEIGHT),
        # Background
        '<rect width="%d" height="%d" fill="white"/>' % (GRID_WIDTH, GRID_HEIGHT),
        # Header
        '<rect width="%d" height="40" fill="%s"/>' % (GRID_WIDTH, color),
        '<text x="10" y="27" font-family="Arial" font-size="16" font-weight="bold" '
        'fill="white">%s</text>' % _escape_svg(genre.replace("_", " ").title()),
        '<text x="%d" y="27" text-anchor="end" font-family="Arial" font-size="12" '
        'fill="white" opacity="0.8">%d ads</text>' % (GRID_WIDTH - 10, len(ad_entries)),
    ]

    for i, entry in enumerate(ad_entries[:9]):
        row = i // GRID_COLS
        col = i % GRID_COLS
        x = col * CELL_SIZE
        y = row * CELL_SIZE + 40

        ad_id = entry.get("ad_id", 0)
        title = _escape_svg(entry.get("title", "")[:20])
        score = entry.get("score", 0)

        # Cell background
        parts.append(
            '<rect x="%d" y="%d" width="%d" height="%d" fill="#f5f5f5" stroke="#e0e0e0"/>'
            % (x, y, CELL_SIZE, CELL_SIZE)
        )

        # Thumbnail reference or placeholder
        has_thumb = entry.get("thumb_path") and os.path.exists(entry.get("thumb_path", ""))
        if has_thumb:
            # SVG can't embed local images easily, show reference
            parts.append(
                '<text x="%d" y="%d" text-anchor="middle" font-family="Arial" font-size="11" '
                'fill="#666">Ad #%d</text>' % (x + CELL_SIZE // 2, y + CELL_SIZE // 2 - 10, ad_id)
            )
            parts.append(
                '<text x="%d" y="%d" text-anchor="middle" font-family="Arial" font-size="10" '
                'fill="#4CAF50">[cached]</text>' % (x + CELL_SIZE // 2, y + CELL_SIZE // 2 + 10)
            )
        else:
            parts.append(
                '<text x="%d" y="%d" text-anchor="middle" font-family="Arial" font-size="11" '
                'fill="#999">Ad #%d</text>' % (x + CELL_SIZE // 2, y + CELL_SIZE // 2, ad_id)
            )

        # Title
        if title:
            parts.append(
                '<text x="%d" y="%d" text-anchor="middle" font-family="Arial" font-size="10" '
                'fill="#333">%s</text>' % (x + CELL_SIZE // 2, y + CELL_SIZE - 12, title)
            )

        # Score badge
        if score > 0:
            badge_color = "#4CAF50" if score >= 70 else "#FF9800" if score >= 40 else "#F44336"
            parts.append(
                '<rect x="%d" y="%d" width="36" height="18" rx="9" fill="%s"/>'
                % (x + CELL_SIZE - 42, y + 6, badge_color)
            )
            parts.append(
                '<text x="%d" y="%d" text-anchor="middle" font-family="Arial" font-size="10" '
                'font-weight="bold" fill="white">%.0f</text>'
                % (x + CELL_SIZE - 24, y + 19, score)
            )

    parts.append('</svg>')
    return '\n'.join(parts)


def main():
    os.makedirs(GRID_DIR, exist_ok=True)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        print("Loaded %d ads" % len(ads))

        # Group by genre with scores
        genre_ads: dict[str, list[dict]] = defaultdict(list)
        for ad in ads:
            meta = ad.ad_metadata or {}
            genre = meta.get("fine_genre_en", "unknown")

            try:
                score = float(meta.get("latest_hit_score", 0) or 0)
            except (ValueError, TypeError):
                score = 0

            thumb_path = os.path.join(THUMB_DIR, "%d.jpg" % ad.id)

            genre_ads[genre].append({
                "ad_id": ad.id,
                "title": ad.title or "",
                "score": score,
                "thumb_path": thumb_path,
            })

        # Sort each genre by score descending
        for genre in genre_ads:
            genre_ads[genre].sort(key=lambda x: x["score"], reverse=True)

        print("Found %d genres" % len(genre_ads))

        generated = 0
        for genre, entries in sorted(genre_ads.items(), key=lambda x: -len(x[1])):
            if len(entries) < 1:
                continue

            color = GENRE_COLORS.get(genre, GENRE_COLORS["default"])
            top9 = entries[:9]

            # Try Pillow first
            if _try_pillow_grid(genre, top9, color):
                print("  [PIL] Generated grid for %s (%d ads)" % (genre, len(entries)))
            else:
                # SVG fallback
                svg = _generate_svg_grid(genre, top9, color)
                svg_path = os.path.join(GRID_DIR, "%s.svg" % genre)
                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(svg)
                print("  [SVG] Generated grid for %s (%d ads)" % (genre, len(entries)))

            generated += 1

        print("\n=== Thumbnail Grid Generation ===")
        print("Generated %d genre grids" % generated)
        print("Output directory: %s" % GRID_DIR)

    except Exception as e:
        print("ERROR: %s" % str(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
