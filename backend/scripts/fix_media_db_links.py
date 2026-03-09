"""Fix media_cache <-> DB linkage.

Scans media_cache/ directories and updates ads table with correct
local file paths so the /media/* endpoints can serve files.
Also updates media_extraction_status accordingly.
"""
import os
import sqlite3
import sys

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "media_cache")


def scan_files(subdir: str, ext: str) -> dict[int, str]:
    """Return {ad_id: filename} for files in media_cache/<subdir>/."""
    dirpath = os.path.join(CACHE_DIR, subdir)
    result = {}
    if not os.path.isdir(dirpath):
        return result
    for f in os.listdir(dirpath):
        if f.endswith(f".{ext}"):
            try:
                ad_id = int(f.replace(f".{ext}", ""))
                result[ad_id] = f
            except ValueError:
                pass
    return result


def main():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    # Get all ad IDs
    cur.execute("SELECT id FROM ads")
    all_ids = {r[0] for r in cur.fetchall()}

    images = scan_files("images", "jpg")
    videos_mp4 = scan_files("videos", "mp4")
    videos_webm = scan_files("videos", "webm")
    thumbnails = scan_files("thumbnails", "jpg")

    videos = {**videos_webm, **videos_mp4}  # mp4 takes priority

    updated = 0

    for ad_id in all_ids:
        updates = []
        params = []

        has_img = ad_id in images
        has_vid = ad_id in videos
        has_thumb = ad_id in thumbnails

        if has_img:
            updates.append("image_s3_key = ?")
            params.append(f"media_cache/images/{images[ad_id]}")

        if has_vid:
            updates.append("video_s3_key = ?")
            params.append(f"media_cache/videos/{videos[ad_id]}")

        if has_thumb:
            updates.append("thumbnail_s3_key = ?")
            params.append(f"media_cache/thumbnails/{thumbnails[ad_id]}")

        if has_img or has_vid or has_thumb:
            # Determine status
            if has_vid or has_img:
                status = "completed"
            else:
                status = "completed"  # thumbnail only is still completed
            updates.append("media_extraction_status = ?")
            params.append(status)

            params.append(ad_id)
            sql = f"UPDATE ads SET {', '.join(updates)} WHERE id = ?"
            cur.execute(sql, params)
            updated += 1

    conn.commit()

    # Stats
    cur.execute("SELECT COUNT(*) FROM ads WHERE image_s3_key IS NOT NULL")
    img_linked = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ads WHERE video_s3_key IS NOT NULL")
    vid_linked = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ads WHERE thumbnail_s3_key IS NOT NULL")
    thumb_linked = cur.fetchone()[0]
    cur.execute("SELECT media_extraction_status, COUNT(*) FROM ads GROUP BY media_extraction_status")
    status_dist = cur.fetchall()

    conn.close()

    print(f"Updated {updated} ads")
    print(f"  image_s3_key linked: {img_linked}")
    print(f"  video_s3_key linked: {vid_linked}")
    print(f"  thumbnail_s3_key linked: {thumb_linked}")
    print(f"  Status distribution: {status_dist}")


if __name__ == "__main__":
    main()
