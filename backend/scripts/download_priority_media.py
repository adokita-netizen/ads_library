"""Download media for top hit ads and remaining videos.

Priority: videos first, then top-scoring ads' images/thumbnails.
"""
import os
import sys
import sqlite3
import time
import urllib.request
import ssl

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")
CACHE_DIR = os.path.join(os.path.dirname(__file__), "..", "media_cache")

# Skip SSL verification for expired CDN certs
ssl_ctx = ssl.create_default_context()
ssl_ctx.check_hostname = False
ssl_ctx.verify_mode = ssl.CERT_NONE


def download_file(url: str, dest_path: str, timeout: int = 30) -> bool:
    """Download a file from URL to dest_path. Returns True on success."""
    if os.path.exists(dest_path):
        return True
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        })
        with urllib.request.urlopen(req, timeout=timeout, context=ssl_ctx) as resp:
            if resp.status != 200:
                return False
            content = resp.read()
            if len(content) < 100:
                return False
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            with open(dest_path, "wb") as f:
                f.write(content)
            return True
    except Exception as e:
        return False


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    stats = {"video_ok": 0, "video_fail": 0, "image_ok": 0, "image_fail": 0, "thumb_ok": 0, "thumb_fail": 0}

    # 1. Download remaining videos (4 uncached)
    print("=== Downloading remaining videos ===")
    cur.execute("""
        SELECT id, video_url FROM ads
        WHERE video_url IS NOT NULL AND video_s3_key IS NULL
        LIMIT 10
    """)
    for row in cur.fetchall():
        ad_id, url = row["id"], row["video_url"]
        dest = os.path.join(CACHE_DIR, "videos", f"{ad_id}.mp4")
        ok = download_file(url, dest)
        if ok:
            cur.execute("UPDATE ads SET video_s3_key = ? WHERE id = ?",
                        (f"media_cache/videos/{ad_id}.mp4", ad_id))
            stats["video_ok"] += 1
            print(f"  Video {ad_id}: OK")
        else:
            stats["video_fail"] += 1
            print(f"  Video {ad_id}: FAIL")
        time.sleep(0.5)

    # 2. Download images/thumbnails for TOP 100 hit ads
    print("\n=== Downloading top hit ad images ===")
    cur.execute("""
        SELECT a.id, a.image_url, a.thumbnail_url
        FROM ads a
        JOIN ad_analyses an ON a.id = an.ad_id
        WHERE an.winning_score >= 25
        AND a.image_s3_key IS NULL
        AND a.image_url IS NOT NULL
        ORDER BY an.winning_score DESC
        LIMIT 100
    """)
    rows = cur.fetchall()
    for row in rows:
        ad_id = row["id"]

        # Image
        if row["image_url"]:
            dest = os.path.join(CACHE_DIR, "images", f"{ad_id}.jpg")
            ok = download_file(row["image_url"], dest)
            if ok:
                cur.execute("UPDATE ads SET image_s3_key = ? WHERE id = ?",
                            (f"media_cache/images/{ad_id}.jpg", ad_id))
                stats["image_ok"] += 1
            else:
                stats["image_fail"] += 1

        # Thumbnail
        if row["thumbnail_url"] and not os.path.exists(os.path.join(CACHE_DIR, "thumbnails", f"{ad_id}.jpg")):
            dest = os.path.join(CACHE_DIR, "thumbnails", f"{ad_id}.jpg")
            ok = download_file(row["thumbnail_url"], dest)
            if ok:
                cur.execute("UPDATE ads SET thumbnail_s3_key = ? WHERE id = ?",
                            (f"media_cache/thumbnails/{ad_id}.jpg", ad_id))
                stats["thumb_ok"] += 1
            else:
                stats["thumb_fail"] += 1

        # Update extraction status
        cur.execute("""
            UPDATE ads SET media_extraction_status = 'completed'
            WHERE id = ? AND (image_s3_key IS NOT NULL OR video_s3_key IS NOT NULL)
        """, (ad_id,))

        time.sleep(0.3)

    conn.commit()

    # Final stats
    cur.execute("SELECT COUNT(*) FROM ads WHERE image_s3_key IS NOT NULL")
    total_img = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM ads WHERE video_s3_key IS NOT NULL")
    total_vid = cur.fetchone()[0]
    cur.execute("SELECT media_extraction_status, COUNT(*) FROM ads GROUP BY media_extraction_status")
    status_dist = cur.fetchall()

    conn.close()

    print(f"\n=== Results ===")
    print(f"Videos: {stats['video_ok']} OK, {stats['video_fail']} failed")
    print(f"Images: {stats['image_ok']} OK, {stats['image_fail']} failed")
    print(f"Thumbs: {stats['thumb_ok']} OK, {stats['thumb_fail']} failed")
    print(f"Total cached images: {total_img}")
    print(f"Total cached videos: {total_vid}")
    print(f"Status distribution: {[(dict(r)['media_extraction_status'], dict(r)['COUNT(*)']) for r in status_dist]}")


if __name__ == "__main__":
    main()
