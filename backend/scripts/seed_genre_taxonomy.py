#!/usr/bin/env python3
"""Seed genre taxonomy and migrate existing genre classifications.

Usage:
    cd C:/Users/ishit/ads_library/backend
    python scripts/seed_genre_taxonomy.py
"""

import os
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text as sa_text
from sqlalchemy.orm.attributes import flag_modified

from app.core.database import SyncSessionLocal, sync_engine, Base
from app.models.creative_asset import GenreTaxonomy, AdGenreTag, CreativeAsset, CreativeFamily
from app.models.ad import Ad


# ── Genre hierarchy definition ──────────────────────────────────────────
GENRE_TREE = [
    # (code, name_ja, name_en, parent_code, level, sort_order)
    # Level 0: Top categories
    ("beauty", "美容系", "Beauty", None, 0, 10),
    ("health", "健康系", "Health", None, 0, 20),
    ("finance", "金融系", "Finance", None, 0, 30),
    ("business", "ビジネス系", "Business", None, 0, 40),
    ("lifestyle", "ライフスタイル系", "Lifestyle", None, 0, 50),
    ("other", "その他", "Other", None, 0, 99),

    # Level 1: Beauty
    ("skincare", "スキンケア", "Skincare", "beauty", 1, 11),
    ("beauty_clinic", "美容クリニック", "Beauty Clinic", "beauty", 1, 12),
    ("hair_removal", "脱毛", "Hair Removal", "beauty", 1, 13),
    ("hair_growth_aga", "育毛・AGA", "Hair Growth / AGA", "beauty", 1, 14),
    ("cosmetics", "コスメ", "Cosmetics", "beauty", 1, 15),
    ("medical_weight_loss", "医療痩身", "Medical Weight Loss", "beauty", 1, 16),

    # Level 1: Health
    ("health_food", "健康食品", "Health Food", "health", 1, 21),
    ("diet_supplement", "ダイエットサプリ", "Diet Supplement", "health", 1, 22),
    ("fitness", "フィットネス", "Fitness", "health", 1, 23),
    ("yoga_pilates", "ヨガ・ピラティス", "Yoga / Pilates", "health", 1, 24),
    ("protein_supplement", "プロテイン", "Protein Supplement", "health", 1, 25),

    # Level 1: Finance
    ("finance_investment", "金融・投資", "Finance & Investment", "finance", 1, 31),

    # Level 1: Business
    ("education_school", "教育・スクール", "Education / School", "business", 1, 41),
    ("jobs_recruitment", "転職・求人", "Jobs / Recruitment", "business", 1, 42),
    ("real_estate", "不動産", "Real Estate", "business", 1, 43),

    # Level 1: Lifestyle
    ("ec_shopping", "ECショッピング", "EC Shopping", "lifestyle", 1, 51),
    ("app", "アプリ", "App", "lifestyle", 1, 52),
    ("short_drama", "ショートドラマ", "Short Drama", "lifestyle", 1, 53),
    ("manga_webtoon", "マンガ・ウェブトゥーン", "Manga / Webtoon", "lifestyle", 1, 54),
    ("gaming_entertainment", "ゲーム・エンタメ", "Gaming / Entertainment", "lifestyle", 1, 55),
]


def seed_genres(session):
    """Insert genre taxonomy rows, skipping existing ones."""
    existing = {g.code for g in session.query(GenreTaxonomy).all()}
    code_to_id = {}

    # First pass: insert level-0 (parents)
    for code, name_ja, name_en, parent_code, level, sort_order in GENRE_TREE:
        if level == 0 and code not in existing:
            genre = GenreTaxonomy(
                code=code, name_ja=name_ja, name_en=name_en,
                level=level, sort_order=sort_order, is_active=True,
            )
            session.add(genre)
            session.flush()
            code_to_id[code] = genre.id
            print(f"  + {code} ({name_ja})")
        elif code in existing:
            row = session.query(GenreTaxonomy).filter_by(code=code).first()
            if row:
                code_to_id[code] = row.id

    # Second pass: insert level-1 (children)
    for code, name_ja, name_en, parent_code, level, sort_order in GENRE_TREE:
        if level == 1 and code not in existing:
            parent_id = code_to_id.get(parent_code)
            genre = GenreTaxonomy(
                code=code, name_ja=name_ja, name_en=name_en,
                parent_genre_id=parent_id, level=level,
                sort_order=sort_order, is_active=True,
            )
            session.add(genre)
            session.flush()
            code_to_id[code] = genre.id
            print(f"  + {code} ({name_ja}) -> parent={parent_code}")
        elif code in existing:
            row = session.query(GenreTaxonomy).filter_by(code=code).first()
            if row:
                code_to_id[code] = row.id

    session.commit()
    total = session.query(GenreTaxonomy).count()
    print(f"\nGenre taxonomy: {total} genres total ({len(GENRE_TREE) - len(existing)} new)")
    return code_to_id


def migrate_genre_tags(session, code_to_id):
    """Migrate existing metadata.fine_genre_en into ad_genre_tags table."""
    # Get all ads with fine_genre_en in metadata
    rows = session.execute(sa_text(
        'SELECT id, json_extract(metadata, "$.fine_genre_en") as fg '
        'FROM ads WHERE json_extract(metadata, "$.fine_genre_en") IS NOT NULL'
    )).fetchall()

    existing_tags = set()
    for row in session.query(AdGenreTag).all():
        existing_tags.add((row.ad_id, row.genre_code))

    created = 0
    skipped = 0
    for ad_id, fg in rows:
        if not fg:
            continue
        genre_code = str(fg).strip().lower()
        if (ad_id, genre_code) in existing_tags:
            skipped += 1
            continue
        if genre_code not in code_to_id and genre_code != "other":
            # Map to 'other' if unknown
            genre_code = "other"

        tag = AdGenreTag(
            ad_id=ad_id,
            genre_code=genre_code,
            confidence=1.0,
            source="keyword",
            is_primary=True,
        )
        session.add(tag)
        existing_tags.add((ad_id, genre_code))
        created += 1

    session.commit()
    print(f"\nGenre tags migration: {created} created, {skipped} skipped (existing)")


def main():
    print("=" * 60)
    print("Genre Taxonomy Seed & Migration")
    print(f"Executed at: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 60)

    # Create tables if needed
    print("\nEnsuring tables exist...")
    Base.metadata.create_all(sync_engine, tables=[
        GenreTaxonomy.__table__,
        CreativeFamily.__table__,
        CreativeAsset.__table__,
        AdGenreTag.__table__,
    ])
    print("  Tables ready.")

    session = SyncSessionLocal()
    try:
        print("\n--- Seeding Genre Taxonomy ---")
        code_to_id = seed_genres(session)

        print("\n--- Migrating Genre Tags ---")
        migrate_genre_tags(session, code_to_id)

        # Summary
        total_ads = session.execute(sa_text("SELECT COUNT(*) FROM ads")).scalar()
        tagged_ads = session.execute(sa_text("SELECT COUNT(DISTINCT ad_id) FROM ad_genre_tags")).scalar()
        print(f"\n--- Summary ---")
        print(f"  Total ads: {total_ads}")
        print(f"  Tagged ads: {tagged_ads}")
        print(f"  Untagged: {total_ads - tagged_ads}")
        print(f"\nDone!")

    except Exception as e:
        session.rollback()
        print(f"ERROR: {e}")
        raise
    finally:
        session.close()


if __name__ == "__main__":
    main()
