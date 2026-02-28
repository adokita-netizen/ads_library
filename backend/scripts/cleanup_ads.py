"""広告データクリーンアップ: 海外広告削除 + 重複削除 + creative_type修正"""
import sqlite3
import re
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "vaap_local.db")

db = sqlite3.connect(DB_PATH)
db.row_factory = sqlite3.Row
c = db.cursor()

# ========================================
# STEP 1: 非日本語広告の削除
# ========================================
print("=" * 60)
print("STEP 1: 非日本語広告の削除")
print("=" * 60)

c.execute("SELECT id, advertiser_name, title, description FROM ads")
rows = c.fetchall()

non_jp_ids = []
for r in rows:
    title = r["title"] or ""
    adv = r["advertiser_name"] or ""
    desc = r["description"] or ""
    combined = title + " " + adv + " " + desc
    has_jp = bool(re.search(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]", combined))
    if not has_jp and combined.strip():
        non_jp_ids.append(r["id"])

print(f"非日本語広告: {len(non_jp_ids)}件")

if non_jp_ids:
    placeholders = ",".join("?" * len(non_jp_ids))
    for table in ["ad_daily_metrics", "product_rankings"]:
        c.execute(f"SELECT count(*) FROM {table} WHERE ad_id IN ({placeholders})", non_jp_ids)
        cnt = c.fetchone()[0]
        if cnt > 0:
            c.execute(f"DELETE FROM {table} WHERE ad_id IN ({placeholders})", non_jp_ids)
            print(f"  {table}: {cnt}件 削除")

    c.execute(f"DELETE FROM ads WHERE id IN ({placeholders})", non_jp_ids)
    print(f"  ads: {c.rowcount}件 削除")
    db.commit()

c.execute("SELECT count(*) FROM ads")
print(f"  残り広告数: {c.fetchone()[0]}件")

# ========================================
# STEP 2: 重複広告の削除（同タイトル×同広告主 → 最古1件を残す）
# ========================================
print()
print("=" * 60)
print("STEP 2: 重複広告の削除（同タイトル×同広告主 → 最古1件を残す）")
print("=" * 60)

c.execute("""
    SELECT title, advertiser_name, GROUP_CONCAT(id) as ids, count(*) as cnt
    FROM ads
    WHERE title IS NOT NULL AND title != ''
    GROUP BY title, advertiser_name
    HAVING cnt > 1
    ORDER BY cnt DESC
""")
dup_groups = c.fetchall()

total_dup_delete = 0
for g in dup_groups:
    ids = [int(x) for x in g["ids"].split(",")]
    keep_id = min(ids)
    delete_ids = [i for i in ids if i != keep_id]

    if delete_ids:
        ph = ",".join("?" * len(delete_ids))
        for table in ["ad_daily_metrics", "product_rankings"]:
            c.execute(f"DELETE FROM {table} WHERE ad_id IN ({ph})", delete_ids)
        c.execute(f"DELETE FROM ads WHERE id IN ({ph})", delete_ids)
        total_dup_delete += len(delete_ids)

db.commit()
print(f"  重複グループ数: {len(dup_groups)}")
print(f"  削除件数: {total_dup_delete}件")

c.execute("SELECT count(*) FROM ads")
print(f"  残り広告数: {c.fetchone()[0]}件")

# ========================================
# STEP 3: creative_type=unknown の修正
# ========================================
print()
print("=" * 60)
print("STEP 3: creative_type=unknown の修正")
print("=" * 60)

c.execute("""
    UPDATE ads SET creative_type = 'video'
    WHERE creative_type = 'unknown'
    AND video_url IS NOT NULL AND video_url != ''
""")
print(f"  unknown -> video: {c.rowcount}件")

c.execute("""
    UPDATE ads SET creative_type = 'image'
    WHERE creative_type = 'unknown'
    AND (image_url IS NOT NULL AND image_url != '')
""")
print(f"  unknown -> image (image_url有): {c.rowcount}件")

c.execute("""
    UPDATE ads SET creative_type = 'image'
    WHERE creative_type = 'unknown'
    AND (thumbnail_url IS NOT NULL AND thumbnail_url != '')
""")
print(f"  unknown -> image (thumbnail有): {c.rowcount}件")

# 残りのunknown（何もURLなし）
c.execute("SELECT count(*) FROM ads WHERE creative_type = 'unknown'")
remaining_unknown = c.fetchone()[0]
if remaining_unknown > 0:
    c.execute("DELETE FROM ads WHERE creative_type = 'unknown' AND image_url IS NULL AND video_url IS NULL AND thumbnail_url IS NULL")
    print(f"  URLなしunknown削除: {c.rowcount}件")

db.commit()

# ========================================
# 最終サマリ
# ========================================
print()
print("=" * 60)
print("最終結果")
print("=" * 60)

c.execute("SELECT count(*) FROM ads")
print(f"総広告数: {c.fetchone()[0]}")

c.execute("SELECT creative_type, count(*) as cnt FROM ads GROUP BY creative_type ORDER BY cnt DESC")
print("creative_type分布:")
for r in c.fetchall():
    print(f"  {r[0] or 'NULL'}: {r[1]}")

c.execute('SELECT count(*) FROM ads WHERE image_url IS NOT NULL AND image_url != ""')
print(f"image_url あり: {c.fetchone()[0]}")
c.execute('SELECT count(*) FROM ads WHERE video_url IS NOT NULL AND video_url != ""')
print(f"video_url あり: {c.fetchone()[0]}")
c.execute('SELECT count(*) FROM ads WHERE thumbnail_url IS NOT NULL AND thumbnail_url != ""')
print(f"thumbnail_url あり: {c.fetchone()[0]}")

# 残りの非日本語チェック
c.execute("SELECT id, title, advertiser_name FROM ads")
remaining_non_jp = 0
for r in c.fetchall():
    combined = (r["title"] or "") + " " + (r["advertiser_name"] or "")
    if not re.search(r"[\u3040-\u309f\u30a0-\u30ff\u4e00-\u9faf]", combined) and combined.strip():
        remaining_non_jp += 1
print(f"非日本語広告残り: {remaining_non_jp}件")

c.execute('SELECT count(*) FROM ads WHERE creative_type = "unknown"')
print(f"creative_type=unknown残り: {c.fetchone()[0]}件")

c.execute("SELECT count(*) FROM ad_daily_metrics")
print(f"ad_daily_metrics残り: {c.fetchone()[0]}件")
c.execute("SELECT count(*) FROM product_rankings")
print(f"product_rankings残り: {c.fetchone()[0]}件")

db.close()
print()
print("完了!")
