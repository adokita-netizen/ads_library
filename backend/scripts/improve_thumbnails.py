"""Resize and optimize cached thumbnails for consistent display.

For all cached thumbnails:
  1. Resize to consistent dimensions (max 640x640, preserve aspect ratio)
  2. Convert PNG/WebP/GIF to JPEG for consistency
  3. Optimize JPEG quality (85%)
  4. Skip files that are already optimized

Requires Pillow (PIL) library. Skips gracefully if not installed.

Run from the backend directory:
    cd backend
    python scripts/improve_thumbnails.py
"""

import os
import sys
import logging

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

logger = logging.getLogger(__name__)

# -- Check Pillow availability --
try:
    from PIL import Image
    PILLOW_AVAILABLE = True
except ImportError:
    PILLOW_AVAILABLE = False

# -- Config --
MAX_DIMENSION = 640       # max width or height (preserve aspect ratio)
JPEG_QUALITY = 85         # JPEG compression quality
MIN_FILE_SIZE = 500       # bytes - skip tiny files
MAX_FILE_SIZE_BEFORE = 5 * 1024 * 1024  # 5MB - skip huge files (likely not thumbnails)

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CACHE_DIR = os.path.join(BASE_DIR, "media_cache")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbnails")
IMAGE_DIR = os.path.join(CACHE_DIR, "images")


def optimize_image(path: str, max_dim: int = MAX_DIMENSION, quality: int = JPEG_QUALITY) -> dict:
    """Resize and optimize a single image file.

    Returns dict with: optimized (bool), original_size, new_size, original_dims, new_dims
    """
    result = {
        "optimized": False,
        "original_size": 0,
        "new_size": 0,
        "original_dims": (0, 0),
        "new_dims": (0, 0),
        "converted_format": False,
        "error": None,
    }

    if not os.path.exists(path):
        result["error"] = "file does not exist"
        return result

    original_size = os.path.getsize(path)
    result["original_size"] = original_size

    if original_size < MIN_FILE_SIZE:
        result["error"] = "file too small"
        return result

    if original_size > MAX_FILE_SIZE_BEFORE:
        result["error"] = "file too large to optimize"
        return result

    try:
        img = Image.open(path)
        result["original_dims"] = img.size
        w, h = img.size

        needs_resize = w > max_dim or h > max_dim
        needs_convert = img.format != "JPEG" and img.format != "MPO"

        if not needs_resize and not needs_convert and original_size < 200 * 1024:
            # Already small JPEG, no optimization needed
            result["new_size"] = original_size
            result["new_dims"] = (w, h)
            img.close()
            return result

        # Resize if needed (preserve aspect ratio)
        if needs_resize:
            img.thumbnail((max_dim, max_dim), Image.Resampling.LANCZOS)

        # Convert to RGB if needed (e.g., RGBA, P mode)
        if img.mode in ("RGBA", "P", "LA", "PA"):
            background = Image.new("RGB", img.size, (255, 255, 255))
            if img.mode == "P":
                img = img.convert("RGBA")
            background.paste(img, mask=img.split()[-1] if "A" in img.mode else None)
            img = background
            result["converted_format"] = True
        elif img.mode != "RGB":
            img = img.convert("RGB")
            result["converted_format"] = True

        result["new_dims"] = img.size

        # Save optimized JPEG
        # Write to temp file first to avoid corruption on failure
        temp_path = path + ".tmp"
        img.save(temp_path, "JPEG", quality=quality, optimize=True)
        img.close()

        new_size = os.path.getsize(temp_path)
        result["new_size"] = new_size

        # Only replace if new file is reasonable
        if new_size >= MIN_FILE_SIZE:
            os.replace(temp_path, path)
            result["optimized"] = True
        else:
            os.remove(temp_path)
            result["error"] = "optimized file too small"
            result["new_size"] = original_size

    except Exception as e:
        result["error"] = str(e)
        # Clean up temp file if it exists
        temp_path = path + ".tmp"
        if os.path.exists(temp_path):
            os.remove(temp_path)

    return result


def main():
    print("=" * 60)
    print("  THUMBNAIL QUALITY IMPROVEMENT")
    print("=" * 60)

    if not PILLOW_AVAILABLE:
        print("\n  Pillow (PIL) is not installed.")
        print("  Install with: pip install Pillow")
        print("  Skipping thumbnail optimization.")
        return

    print(f"  Settings: max_dim={MAX_DIMENSION}, quality={JPEG_QUALITY}")
    print()

    stats = {
        "total_files": 0,
        "optimized": 0,
        "skipped": 0,
        "errors": 0,
        "total_saved_bytes": 0,
        "format_converted": 0,
        "resized": 0,
    }

    # Process thumbnails
    print("  Processing thumbnails...")
    if os.path.isdir(THUMB_DIR):
        files = sorted([f for f in os.listdir(THUMB_DIR) if f.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))])
        stats["total_files"] += len(files)

        for i, fname in enumerate(files):
            path = os.path.join(THUMB_DIR, fname)
            result = optimize_image(path)

            if result["error"]:
                stats["errors"] += 1
                if "too small" not in result["error"] and "too large" not in result["error"]:
                    print(f"    ERROR {fname}: {result['error']}")
            elif result["optimized"]:
                stats["optimized"] += 1
                saved = result["original_size"] - result["new_size"]
                stats["total_saved_bytes"] += saved
                if result["converted_format"]:
                    stats["format_converted"] += 1
                orig_w, orig_h = result["original_dims"]
                new_w, new_h = result["new_dims"]
                if orig_w != new_w or orig_h != new_h:
                    stats["resized"] += 1
            else:
                stats["skipped"] += 1

            if (i + 1) % 50 == 0:
                print(f"    ... processed {i + 1}/{len(files)} thumbnails")

    # Process images
    print("  Processing images...")
    if os.path.isdir(IMAGE_DIR):
        files = sorted([f for f in os.listdir(IMAGE_DIR) if f.endswith((".jpg", ".jpeg", ".png", ".webp", ".gif"))])
        stats["total_files"] += len(files)

        for i, fname in enumerate(files):
            path = os.path.join(IMAGE_DIR, fname)
            # Use larger max dimension for full images
            result = optimize_image(path, max_dim=1280, quality=JPEG_QUALITY)

            if result["error"]:
                stats["errors"] += 1
                if "too small" not in result["error"] and "too large" not in result["error"]:
                    print(f"    ERROR {fname}: {result['error']}")
            elif result["optimized"]:
                stats["optimized"] += 1
                saved = result["original_size"] - result["new_size"]
                stats["total_saved_bytes"] += saved
                if result["converted_format"]:
                    stats["format_converted"] += 1
                orig_w, orig_h = result["original_dims"]
                new_w, new_h = result["new_dims"]
                if orig_w != new_w or orig_h != new_h:
                    stats["resized"] += 1
            else:
                stats["skipped"] += 1

            if (i + 1) % 50 == 0:
                print(f"    ... processed {i + 1}/{len(files)} images")

    # Report
    print()
    print("=" * 60)
    print("  OPTIMIZATION RESULTS")
    print("=" * 60)
    print(f"  Total files:      {stats['total_files']}")
    print(f"  Optimized:        {stats['optimized']}")
    print(f"  Skipped (OK):     {stats['skipped']}")
    print(f"  Errors:           {stats['errors']}")
    print(f"  Format converted: {stats['format_converted']}")
    print(f"  Resized:          {stats['resized']}")
    saved_kb = stats["total_saved_bytes"] / 1024
    saved_mb = saved_kb / 1024
    if saved_mb > 1:
        print(f"  Space saved:      {saved_mb:.1f} MB")
    else:
        print(f"  Space saved:      {saved_kb:.1f} KB")
    print("=" * 60)


if __name__ == "__main__":
    main()
