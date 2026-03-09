# データ品質視点 — ゴミを入れたらゴミが出る

## なぜデータ品質が最重要か

- VAAPの価値は「正確なヒット広告の判定」
- データが汚い → スコアが不正確 → ユーザーの信頼を失う
- 58件の現状で品質を確保 → スケールしても品質維持

---

## データ品質の7次元

### 1. 完全性（Completeness）

```
必須フィールドの充填率:

ads テーブル:
  ad_archive_id:    100% （Meta APIから取得）
  title:            ?%   （fix_titles.py で修復）
  category:         ?%   （classify_ads.py で分類）
  destination_url:  ?%   （fix_destination_urls.py で修復）
  page_name:        ?%   （Meta APIから取得）
  publisher_platform: ?% （Meta APIから取得）

ad_metadata (JSONB):
  delivery_start:   ?%
  delivery_end:     ?%   （配信中はNULL=正常）
  is_still_running: ?%   （check_ad_survival.py で更新）
  impressions:      ?%   （Meta APIから、range形式）
  spend:            ?%   （Meta APIから、range形式）

product_rankings:
  hit_score:        ?%   （recompute_hit_scores.py で計算）
  category:         ?%   （adsから継承）

確認コマンド:
  python -c "
  from app.core.database import SyncSessionLocal
  from app.models.ad import Ad
  s = SyncSessionLocal()
  total = s.query(Ad).count()
  with_title = s.query(Ad).filter(Ad.title != None, Ad.title != '').count()
  with_cat = s.query(Ad).filter(Ad.category != None).count()
  with_dest = s.query(Ad).filter(Ad.destination_url != None).count()
  print(f'Total: {total}')
  print(f'Title: {with_title}/{total} ({with_title/total*100:.0f}%)')
  print(f'Category: {with_cat}/{total} ({with_cat/total*100:.0f}%)')
  print(f'Dest URL: {with_dest}/{total} ({with_dest/total*100:.0f}%)')
  s.close()
  "
```

### 2. 正確性（Accuracy）

```
問題のあるデータ:
  - title が広告テキストの全文になっている（長すぎる）
  - category が「その他」に大量に分類されている
  - destination_url がリダイレクト前のURL
  - impressions/spend が range（下限-上限）で精度が低い
  - hit_score の計算に使うデータ自体が不正確

検証方法:
  - title の文字数分布を確認（平均、中央値、最大）
  - category の分布を確認（「その他」が50%以上なら問題）
  - destination_url の HTTP ステータス確認（404多数なら問題）
```

### 3. 鮮度（Timeliness）

```
データの更新頻度:
  - 広告の配信状態: 最終チェック日からの経過日数
  - impressions/spend: 最終取得日からの経過日数
  - hit_score: 最終計算日からの経過日数

鮮度の目標:
  配信状態: 24時間以内
  スコア: 6時間以内（データ変更後）
  メディアURL: 7日以内（URL無効化対策）

確認:
  SELECT
    MAX(updated_at) as last_update,
    NOW() - MAX(updated_at) as staleness
  FROM product_rankings;
```

### 4. 一貫性（Consistency）

```
チェック項目:
  - ads.category と product_rankings.category が一致しているか
  - ads.id と product_rankings.ad_id の参照整合性
  - ad_metadata 内のフィールド名が統一されているか
    × "is_still_running" vs "is_active" vs "active"
  - 日付形式が統一されているか
    × "2025-03-01" vs "2025/03/01" vs "1709312400"
```

### 5. 一意性（Uniqueness）

```
重複チェック:
  - 同じ ad_archive_id の広告が複数存在しないか
  - 同じ広告に複数の product_rankings が存在しないか

  SELECT ad_archive_id, COUNT(*)
  FROM ads
  GROUP BY ad_archive_id
  HAVING COUNT(*) > 1;
```

### 6. 妥当性（Validity）

```
バリデーションルール:
  - hit_score: 0-100 の範囲内
  - delivery_start <= delivery_end（配信停止の場合）
  - destination_url: 有効なURL形式
  - publisher_platform: 既知の値のみ（facebook, instagram, youtube等）
  - category: マスターカテゴリリストに含まれる

  SELECT * FROM product_rankings
  WHERE hit_score < 0 OR hit_score > 100;
```

### 7. アクセシビリティ（Accessibility）

```
データへのアクセスしやすさ:
  - APIで全データにアクセスできるか
  - フィルター/ソート/検索が正しく動くか
  - エクスポートで全フィールドが含まれるか
```

---

## データ品質スコアカード

```
+-------------------+-------+--------+--------+
| 次元              | 現状  | v0.1目標 | v1.0目標 |
+-------------------+-------+--------+--------+
| 完全性            | ?/100 | 80/100 | 95/100 |
| 正確性            | ?/100 | 70/100 | 90/100 |
| 鮮度              | ?/100 | 60/100 | 90/100 |
| 一貫性            | ?/100 | 80/100 | 95/100 |
| 一意性            | ?/100 | 95/100 | 100/100|
| 妥当性            | ?/100 | 85/100 | 95/100 |
| アクセシビリティ   | ?/100 | 70/100 | 90/100 |
+-------------------+-------+--------+--------+
```

---

## データ品質パイプライン

### 取得時のバリデーション

```python
# クロール結果をDBに保存する前にバリデーション

class AdValidator:
    def validate(self, raw_ad: dict) -> tuple[bool, list[str]]:
        errors = []

        # 必須フィールド
        if not raw_ad.get("ad_archive_id"):
            errors.append("ad_archive_id is required")

        # URL形式
        url = raw_ad.get("destination_url")
        if url and not url.startswith(("http://", "https://")):
            errors.append(f"Invalid URL: {url}")

        # 日付形式
        start = raw_ad.get("ad_delivery_start_time")
        if start:
            try:
                datetime.fromisoformat(start)
            except ValueError:
                errors.append(f"Invalid date: {start}")

        # impressions 範囲
        imp = raw_ad.get("impressions", {})
        if imp:
            lower = imp.get("lower_bound", 0)
            upper = imp.get("upper_bound", 0)
            if lower > upper:
                errors.append(f"Invalid impressions range: {lower} > {upper}")

        return len(errors) == 0, errors
```

### 定期的な品質チェック

```python
# scripts/check_data_quality.py

class DataQualityChecker:
    def __init__(self, db):
        self.db = db
        self.issues = []

    def check_all(self):
        self.check_completeness()
        self.check_duplicates()
        self.check_validity()
        self.check_consistency()
        self.check_staleness()
        return self.issues

    def check_completeness(self):
        """必須フィールドの充填率"""
        total = self.db.query(Ad).count()
        checks = {
            "title": Ad.title != None,
            "category": Ad.category != None,
            "destination_url": Ad.destination_url != None,
        }
        for field, condition in checks.items():
            filled = self.db.query(Ad).filter(condition).count()
            rate = filled / total if total > 0 else 0
            if rate < 0.8:
                self.issues.append({
                    "type": "completeness",
                    "field": field,
                    "fill_rate": rate,
                    "severity": "high" if rate < 0.5 else "medium",
                })

    def check_duplicates(self):
        """重複チェック"""
        dupes = self.db.execute(text("""
            SELECT ad_archive_id, COUNT(*)
            FROM ads
            GROUP BY ad_archive_id
            HAVING COUNT(*) > 1
        """)).fetchall()
        if dupes:
            self.issues.append({
                "type": "uniqueness",
                "duplicate_count": len(dupes),
                "severity": "high",
            })

    def check_validity(self):
        """妥当性チェック"""
        invalid_scores = self.db.query(ProductRanking).filter(
            (ProductRanking.hit_score < 0) | (ProductRanking.hit_score > 100)
        ).count()
        if invalid_scores > 0:
            self.issues.append({
                "type": "validity",
                "field": "hit_score",
                "invalid_count": invalid_scores,
                "severity": "critical",
            })

    def check_staleness(self):
        """鮮度チェック"""
        stale = self.db.execute(text("""
            SELECT COUNT(*) FROM product_rankings
            WHERE updated_at < NOW() - INTERVAL '7 days'
        """)).scalar()
        if stale > 0:
            self.issues.append({
                "type": "staleness",
                "stale_count": stale,
                "severity": "medium",
            })
```

---

## データ修復スクリプト一覧

```
scripts/fix_titles.py
  → 長すぎるタイトルを切り詰め、空のタイトルをテキストから推定

scripts/classify_ads.py
  → カテゴリ未分類の広告をキーワードベースで分類

scripts/fix_destination_urls.py
  → destination_url をsnapshot_urlから抽出、リダイレクト先を追跡

scripts/collect_delivery_dates.py
  → 配信開始/終了日をMeta APIまたはad_metadataから取得

scripts/check_ad_survival.py
  → 広告がまだ配信中かMeta APIで確認、is_still_running更新

scripts/recompute_hit_scores.py
  → 全広告のヒットスコアを再計算

scripts/fix_bad_thumbnails.py
  → 壊れたサムネイルURLを修復、再取得
```

---

## 品質ダッシュボード

### 管理画面に表示

```
┌─────────────────────────────────────────┐
│ データ品質ダッシュボード                   │
├─────────────────────────────────────────┤
│                                           │
│ 全体スコア: 72/100  [前回比 +5]           │
│                                           │
│ 充填率:                                   │
│  タイトル:      ████████████░░ 85%        │
│  カテゴリ:      ██████████░░░░ 72%        │
│  LP URL:        ████████░░░░░░ 60%        │
│  サムネイル:    ██████████████ 95%         │
│  ヒットスコア:  ████████████░░ 88%        │
│                                           │
│ 問題:                                     │
│  ⚠ 重複広告: 3件                          │
│  ⚠ スコア範囲外: 0件                      │
│  ⚠ 7日以上未更新: 12件                    │
│  ⚠ カテゴリ「その他」: 28%               │
│                                           │
│ [品質チェック実行]  [修復スクリプト実行]    │
└─────────────────────────────────────────┘
```

---

## 実装優先度

```
[Phase 1: 現状把握]
  1. check_data_quality.py 作成
  2. 全テーブルの充填率レポート
  3. 重複チェック + 修復

[Phase 2: 取得時の品質担保]
  4. AdValidator の実装
  5. クロール時のバリデーション
  6. 不正データのログ記録

[Phase 3: 継続的品質管理]
  7. 品質ダッシュボード（フロント）
  8. 定期品質チェック（Lambda スケジュール）
  9. 品質低下時のアラート
  10. 品質メトリクスの時系列記録
```
