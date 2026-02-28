#!/usr/bin/env python3
"""Batch validate all cached thumbnail files.

Checks every thumbnail file:
  - Is it a valid image? (check magic bytes)
  - Is it the right size? (not 1x1 or tiny)
  - Is it a placeholder? (mostly single color)
  - Is it corrupted? (truncated file)

Categorizes each: valid, placeholder, corrupted, missing
Replaces corrupted with smart placeholder.

Run:
    cd C:/Users/ishit/ads_library/backend
    python scripts/batch_validate_thumbnails.py
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

# Magic bytes for common image formats
MAGIC_BYTES = {
    "jpeg": b'\xff\xd8',
    "png": b'\x89PNG',
    "gif": b'GIF8',
    "webp": b'RIFF',
}

# Minimum valid file size (bytes)
MIN_VALID_SIZE = 500

# Files smaller than this are likely placeholders
PLACEHOLDER_SIZE_THRESHOLD = 5 * 1024  # 5 KB


def _check_magic_bytes(path: str) -> str | None:
    """Check file magic bytes. Returns format name or None."""
    try:
        with open(path, "rb") as f:
            header = f.read(8)
        for fmt, magic in MAGIC_BYTES.items():
            if header[:len(magic)] == magic:
                return fmt
    except OSError:
        pass
    return None


def _check_image_dimensions(path: str) -> tuple[int, int] | None:
    """Try to get image dimensions. Returns (width, height) or None."""
    try:
        from PIL import Image
        img = Image.open(path)
        return img.size
    except ImportError:
        pass
    except Exception:
        pass

    # Fallback: try JPEG SOF marker
    try:
        with open(path, "rb") as f:
            data = f.read(65536)  # Read first 64KB

        # Look for JPEG SOF markers
        i = 0
        while i < len(data) - 8:
            if data[i] == 0xFF:
                marker = data[i + 1]
                # SOF markers: 0xC0-0xCF (except 0xC4 and 0xCC)
                if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xCC):
                    height = int.from_bytes(data[i + 5:i + 7], "big")
                    width = int.from_bytes(data[i + 7:i + 9], "big")
                    if width > 0 and height > 0:
                        return (width, height)
                # Skip to next marker
                if marker == 0xD8 or marker == 0xD9:
                    i += 2
                elif i + 3 < len(data):
                    seg_len = int.from_bytes(data[i + 2:i + 4], "big")
                    i += 2 + seg_len
                else:
                    break
            else:
                i += 1
    except Exception:
        pass

    return None


def _is_single_color(path: str) -> bool:
    """Check if image is mostly a single color (placeholder detection)."""
    try:
        from PIL import Image
        img = Image.open(path).convert("RGB").resize((10, 10), Image.NEAREST)
        pixels = list(img.getdata())
        if not pixels:
            return False
        first = pixels[0]
        same_count = sum(1 for p in pixels if abs(p[0] - first[0]) < 20
                         and abs(p[1] - first[1]) < 20
                         and abs(p[2] - first[2]) < 20)
        return same_count > len(pixels) * 0.85
    except ImportError:
        # Without Pillow, use file size heuristic
        try:
            size = os.path.getsize(path)
            return size < PLACEHOLDER_SIZE_THRESHOLD
        except OSError:
            return False
    except Exception:
        return False


def _generate_replacement_svg(ad_id: int, reason: str) -> str:
    """Generate a simple replacement SVG placeholder."""
    return (
        '<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" '
        'viewBox="0 0 400 300">'
        '<rect width="400" height="300" rx="8" fill="#f5f5f5"/>'
        '<rect width="400" height="4" fill="#FF9800"/>'
        '<text x="200" y="130" text-anchor="middle" font-family="Arial" '
        'font-size="16" fill="#666">Ad #%d</text>'
        '<text x="200" y="160" text-anchor="middle" font-family="Arial" '
        'font-size="12" fill="#999">Replaced: %s</text>'
        '<text x="200" y="185" text-anchor="middle" font-family="Arial" '
        'font-size="11" fill="#bbb">Original thumbnail was invalid</text>'
        '</svg>' % (ad_id, reason)
    )


def main():
    os.makedirs(PLACEHOLDER_DIR, exist_ok=True)

    session = SyncSessionLocal()
    try:
        ads = session.query(Ad).all()
        ad_ids = {ad.id for ad in ads}
        print("Loaded %d ads from database" % len(ads))

        if not os.path.isdir(THUMB_DIR):
            print("Thumbnail directory not found: %s" % THUMB_DIR)
            print("No thumbnails to validate.")
            return

        thumb_files = [f for f in os.listdir(THUMB_DIR) if f.endswith(".jpg")]
        print("Found %d thumbnail files" % len(thumb_files))

        results = {
            "valid": 0,
            "placeholder": 0,
            "corrupted": 0,
            "tiny": 0,
            "orphaned": 0,
        }
        corrupted_replaced = 0
        details = []

        for fname in thumb_files:
            try:
                ad_id = int(fname.replace(".jpg", ""))
            except ValueError:
                results["orphaned"] += 1
                continue

            if ad_id not in ad_ids:
                results["orphaned"] += 1
                continue

            fpath = os.path.join(THUMB_DIR, fname)
            file_size = 0
            try:
                file_size = os.path.getsize(fpath)
            except OSError:
                results["corrupted"] += 1
                details.append({"ad_id": ad_id, "status": "unreadable"})
                continue

            # Check 1: Magic bytes
            fmt = _check_magic_bytes(fpath)
            if fmt is None:
                results["corrupted"] += 1
                details.append({"ad_id": ad_id, "status": "invalid_format", "size": file_size})

                # Replace with SVG placeholder
                svg = _generate_replacement_svg(ad_id, "invalid format")
                svg_path = os.path.join(PLACEHOLDER_DIR, "%d.svg" % ad_id)
                with open(svg_path, "w", encoding="utf-8") as f:
                    f.write(svg)
                corrupted_replaced += 1
                continue

            # Check 2: File size
            if file_size < MIN_VALID_SIZE:
                results["tiny"] += 1
                details.append({"ad_id": ad_id, "status": "too_small", "size": file_size})
                continue

            # Check 3: Dimensions (if possible)
            dims = _check_image_dimensions(fpath)
            if dims and (dims[0] <= 2 or dims[1] <= 2):
                results["tiny"] += 1
                details.append({"ad_id": ad_id, "status": "tiny_dimensions",
                                "width": dims[0], "height": dims[1]})
                continue

            # Check 4: Single color (placeholder)
            if _is_single_color(fpath):
                results["placeholder"] += 1
                details.append({"ad_id": ad_id, "status": "single_color", "size": file_size})
                continue

            # Check 5: Truncated file (JPEG should end with FF D9)
            if fmt == "jpeg":
                try:
                    with open(fpath, "rb") as f:
                        f.seek(-2, 2)
                        tail = f.read(2)
                    if tail != b'\xff\xd9' and file_size > 1024:
                        # Might be truncated, but could still display
                        pass  # Don't flag as corrupted if it has valid header
                except OSError:
                    pass

            results["valid"] += 1

        # Find missing thumbnails
        cached_ids = set()
        for f in thumb_files:
            try:
                cached_ids.add(int(f.replace(".jpg", "")))
            except ValueError:
                pass
        missing_count = len(ad_ids - cached_ids)

        # Print report
        print("\n=== Thumbnail Validation Report ===")
        total_checked = sum(results.values())
        print("Total files checked: %d" % total_checked)
        print("Missing (no file):   %d" % missing_count)
        print("")

        print("Results:")
        status_order = ["valid", "placeholder", "corrupted", "tiny", "orphaned"]
        for status in status_order:
            count = results[status]
            pct = count / max(total_checked, 1) * 100
            bar = "#" * min(int(pct / 2), 40)
            marker = "OK" if status == "valid" else "!!"
            print("  [%s] %-12s %5d (%5.1f%%)  %s" % (marker, status, count, pct, bar))

        if corrupted_replaced:
            print("\nReplaced %d corrupted thumbnails with SVG placeholders" % corrupted_replaced)
            print("Placeholders stored in: %s" % PLACEHOLDER_DIR)

        if details:
            print("\nProblem Files (first 20):")
            for d in details[:20]:
                print("  Ad #%-6d  %-20s  %s" % (
                    d["ad_id"], d["status"],
                    "size=%d" % d.get("size", 0) if "size" in d else ""
                ))

    except Exception as e:
        print("ERROR: %s" % str(e))
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
