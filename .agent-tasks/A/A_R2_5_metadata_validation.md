# A-R2-5: ad_metadata スキーマバリデーション (CI-007)
# 優先度: P0 | 前提: A-R2-1 | ブロック: なし

## 目的
ad_metadata JSON の必須キー欠落を検知し、デイリーレポートとして出力する。

## 対象ファイル
- 新規: `backend/scripts/validate_metadata.py`

## 実装

```python
"""ad_metadata スキーマバリデーション"""
import sys
import json
from datetime import datetime
from collections import defaultdict

sys.path.insert(0, ".")
from app.core.database import SyncSessionLocal
from app.models.ad import Ad

# 必須キー定義（全広告に存在すべき）
REQUIRED_KEYS = [
    "latest_hit_score",
    "is_still_running",
    "days_running",
    "creative_quality",
    "longevity_class",
]

# 推奨キー定義（あれば望ましい）
RECOMMENDED_KEYS = [
    "publisher_platforms",
    "estimation_method",
    "delivery_start_time",
    "freshness_score",
]

def validate():
    session = SyncSessionLocal()
    ads = session.query(Ad).all()
    total = len(ads)

    missing_required = defaultdict(list)  # key -> [ad_ids]
    missing_recommended = defaultdict(list)
    no_metadata = []

    for ad in ads:
        meta = ad.ad_metadata or {}

        if not meta:
            no_metadata.append(ad.id)
            for k in REQUIRED_KEYS:
                missing_required[k].append(ad.id)
            continue

        for k in REQUIRED_KEYS:
            if k not in meta or meta[k] is None:
                missing_required[k].append(ad.id)

        for k in RECOMMENDED_KEYS:
            if k not in meta or meta[k] is None:
                missing_recommended[k].append(ad.id)

    # レポート出力
    print(f"=== ad_metadata Validation Report ===")
    print(f"Date: {datetime.now().isoformat()}")
    print(f"Total ads: {total}")
    print(f"No metadata at all: {len(no_metadata)}")
    print()

    print("--- REQUIRED keys ---")
    all_ok = True
    for k in REQUIRED_KEYS:
        count = len(missing_required[k])
        pct = round(count / total * 100, 1) if total > 0 else 0
        status = "OK" if count == 0 else "WARN"
        if count > 0:
            all_ok = False
        print(f"  [{status}] {k}: {count} missing ({pct}%)")

    print()
    print("--- RECOMMENDED keys ---")
    for k in RECOMMENDED_KEYS:
        count = len(missing_recommended[k])
        pct = round(count / total * 100, 1) if total > 0 else 0
        print(f"  [INFO] {k}: {count} missing ({pct}%)")

    print()
    if all_ok:
        print("Result: ALL REQUIRED KEYS PRESENT")
    else:
        print("Result: VALIDATION WARNINGS FOUND")
        print("Action: Run data quality scripts to fill missing keys")

    session.close()
    return not all_ok  # True if warnings

if __name__ == "__main__":
    has_warnings = validate()
    sys.exit(1 if has_warnings else 0)
```

## 実行
```bash
cd C:/Users/ishit/ads_library/backend
python -m scripts.validate_metadata
```

## 完了条件
- [x] validate_metadata.py が作成され、実行可能
- [ ] 必須キーの欠落率が各5%未満
- [x] レポート出力が構造化されている
- [x] status.md に結果記録
