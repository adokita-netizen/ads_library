"""Generate dummy ad data for load testing.

Usage:
    python scripts/generate_test_data.py [--count N] [--cleanup]

Generates N dummy ads in the database with realistic distributions.
"""

import argparse
import random
import sys
import uuid
from datetime import datetime, timedelta, timezone

# Add parent to path
sys.path.insert(0, ".")

from app.core.database import SyncSessionLocal, sync_engine, Base
from app.models.ad import Ad, AdPlatformEnum, AdStatusEnum

GENRES = [
    "美容・コスメ", "健康食品", "ダイエット", "金融・投資",
    "教育・資格", "転職・求人", "不動産", "ゲーム・アプリ",
    "ファッション", "食品・飲料", "旅行", "エンタメ",
    "IT・テクノロジー", "ペット", "スポーツ",
]

PLATFORMS = list(AdPlatformEnum)
STATUSES = [AdStatusEnum.ANALYZED, AdStatusEnum.PENDING, AdStatusEnum.PROCESSING]

HOOKS = [
    "衝撃の事実", "知らないと損", "たった3日で", "プロが教える",
    "今だけ限定", "驚きの結果", "簡単3ステップ", "無料で始める",
]

CTAS = [
    "詳しくはこちら", "今すぐ申し込む", "無料体験する", "資料請求",
    "ダウンロード", "購入する", "お問い合わせ",
]


def generate_ads(count: int):
    session = SyncSessionLocal()
    try:
        now = datetime.now(timezone.utc)
        batch = []
        for i in range(count):
            genre = random.choice(GENRES)
            platform = random.choice(PLATFORMS)
            days_ago = random.randint(1, 180)
            first_seen = now - timedelta(days=days_ago)
            duration = random.choice([15, 30, 60, 90, 120])
            views = int(random.lognormvariate(10, 2))
            likes = int(views * random.uniform(0.01, 0.1))
            hit_score = random.betavariate(2, 5) * 100

            ad = Ad(
                external_id=f"loadtest_{uuid.uuid4().hex[:12]}",
                title=f"{random.choice(HOOKS)} - {genre}広告テスト{i+1}",
                description=f"負荷テスト用ダミー広告: {genre}",
                platform=platform,
                status=random.choice(STATUSES),
                advertiser_name=f"テスト広告主{random.randint(1, 100)}",
                brand_name=f"テストブランド{random.randint(1, 50)}",
                video_url=f"https://example.com/videos/{uuid.uuid4().hex}.mp4",
                thumbnail_url=f"https://example.com/thumbs/{uuid.uuid4().hex}.jpg",
                duration_seconds=duration,
                view_count=views,
                like_count=likes,
                first_seen_at=first_seen,
                ad_metadata={
                    "genre": genre,
                    "genre_en": genre,
                    "latest_hit_score": round(hit_score, 2),
                    "hook_text": random.choice(HOOKS),
                    "cta_text": random.choice(CTAS),
                    "is_hit": hit_score > 60,
                },
                tags=[genre, random.choice(CTAS)],
            )
            batch.append(ad)

            if len(batch) >= 500:
                session.add_all(batch)
                session.flush()
                print(f"  Inserted {i+1}/{count}...")
                batch = []

        if batch:
            session.add_all(batch)
            session.flush()

        session.commit()
        print(f"Generated {count} test ads.")
    except Exception as e:
        session.rollback()
        print(f"Error: {e}")
        raise
    finally:
        session.close()


def cleanup():
    session = SyncSessionLocal()
    try:
        deleted = session.query(Ad).filter(
            Ad.external_id.like("loadtest_%")
        ).delete(synchronize_session=False)
        session.commit()
        print(f"Deleted {deleted} test ads.")
    finally:
        session.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate test data for VAAP")
    parser.add_argument("--count", type=int, default=1000, help="Number of ads to generate")
    parser.add_argument("--cleanup", action="store_true", help="Remove test data instead")
    args = parser.parse_args()

    if args.cleanup:
        cleanup()
    else:
        generate_ads(args.count)
