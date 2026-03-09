# A-R2-3: Full Data Pipeline Run
# 優先度: P1 | 前提: A-R2-1, A-R2-2 | ブロック: なし

## 目的
全176件に対して全分析スクリプトを一括実行し、データ完全性を100%に近づける。

## 手順

### 一括実行スクリプト
```bash
cd C:/Users/ishit/ads_library/backend

echo "=== Step 1: classify_ads ==="
python -m scripts.classify_ads 2>&1 | tail -5

echo "=== Step 2: fix_titles ==="
python -m scripts.fix_titles 2>&1 | tail -5

echo "=== Step 3: fix_destination_urls ==="
python -m scripts.fix_destination_urls 2>&1 | tail -5

echo "=== Step 4: collect_delivery_dates ==="
python -m scripts.collect_delivery_dates 2>&1 | tail -5

echo "=== Step 5: check_ad_survival ==="
python -m scripts.check_ad_survival 2>&1 | tail -5

echo "=== Step 6: backfill_deltas (A-R2-2 で作成) ==="
python -m scripts.backfill_deltas 2>&1 | tail -5

echo "=== DONE ==="
```

### 実行後のヘルスチェック
```bash
python -c "
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from sqlalchemy import func

session = SyncSessionLocal()
total = session.query(func.count(Ad.id)).scalar()

fields = ['title', 'category', 'destination_url', 'platform', 'advertiser_name', 'creative_type']
print(f'Total: {total}')
for f in fields:
    null_count = session.query(func.count(Ad.id)).filter(getattr(Ad, f) == None).scalar()
    fill_rate = round((total - null_count) / total * 100, 1)
    print(f'  {f}: {fill_rate}% filled ({null_count} NULL)')

session.close()
"
```

## 完了条件
- [ ] 全スクリプトがエラーなく完了
- [ ] 主要フィールドの充填率が95%以上
- [ ] 結果を status.md に記録（各フィールドの充填率）
