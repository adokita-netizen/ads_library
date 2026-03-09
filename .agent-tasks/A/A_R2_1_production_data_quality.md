# A-R2-1: Production Data Quality Fix
# 優先度: P0 | 前提: なし | ブロック: A-R2-2, A-R2-3

## 目的
176件の広告データの NULL / 欠損を 0 に近づける。
ProRankingTable が全カラムにデータを表示できる状態にする。

## 手順

### Step 1: 現状調査
```bash
cd C:/Users/ishit/ads_library/backend
python -c "
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from sqlalchemy import func, case, text

session = SyncSessionLocal()
total = session.query(func.count(Ad.id)).scalar()

checks = {
    'title_null': session.query(func.count(Ad.id)).filter(Ad.title == None).scalar(),
    'title_empty': session.query(func.count(Ad.id)).filter(Ad.title == '').scalar(),
    'category_null': session.query(func.count(Ad.id)).filter(Ad.category == None).scalar(),
    'destination_url_null': session.query(func.count(Ad.id)).filter(Ad.destination_url == None).scalar(),
    'thumbnail_url_null': session.query(func.count(Ad.id)).filter(Ad.thumbnail_url == None).scalar(),
    'image_url_null': session.query(func.count(Ad.id)).filter(Ad.image_url == None).scalar(),
    'video_url_null': session.query(func.count(Ad.id)).filter(Ad.video_url == None).scalar(),
    'creative_type_null': session.query(func.count(Ad.id)).filter(Ad.creative_type == None).scalar(),
    'platform_null': session.query(func.count(Ad.id)).filter(Ad.platform == None).scalar(),
    'advertiser_name_null': session.query(func.count(Ad.id)).filter(Ad.advertiser_name == None).scalar(),
}

print(f'Total ads: {total}')
for k, v in checks.items():
    pct = round(v / total * 100, 1) if total > 0 else 0
    print(f'  {k}: {v} ({pct}%)')

# ad_metadata key check
from sqlalchemy import text as sqlt
required_keys = ['latest_hit_score', 'creative_quality', 'is_still_running', 'days_running', 'longevity_class']
for key in required_keys:
    count = session.execute(sqlt(f\"\"\"
        SELECT COUNT(*) FROM ads
        WHERE ad_metadata IS NULL OR ad_metadata->>'{key}' IS NULL
    \"\"\")).scalar()
    pct = round(count / total * 100, 1) if total > 0 else 0
    print(f'  metadata.{key} missing: {count} ({pct}%)')

session.close()
"
```

### Step 2: NULL修正スクリプト実行
結果に応じて以下を実行:
```bash
# category NULL があれば
python -m scripts.classify_ads

# title NULL/空 があれば
python -m scripts.fix_titles

# destination_url NULL があれば
python -m scripts.fix_destination_urls

# creative_type NULL があれば → Agent D 領域なので COORDINATION_LOG に記載
# thumbnail/image/video URL NULL → Agent D 領域
```

### Step 3: ad_metadata 補完
```bash
# days_running / is_still_running が NULL の場合
python -m scripts.collect_delivery_dates

# longevity_class が NULL の場合
python -m scripts.check_ad_survival
```

### Step 4: ヒットスコア再計算依頼
全データ補完後、COORDINATION_LOG に以下を追記:
```
[Planner 1 → Planner 2] データ補完完了。recompute_hit_scores.py の再実行を依頼。
```

## 完了条件
- [ ] title NULL/空: 0件
- [ ] category NULL: 0件
- [ ] destination_url NULL: 10%未満
- [ ] ad_metadata 必須キー欠落: 各5%未満
- [ ] 調査結果と修正結果を status.md に記録
