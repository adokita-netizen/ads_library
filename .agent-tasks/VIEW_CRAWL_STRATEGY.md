# クロール戦略視点 — 58件→2000件を最速で達成する方法

## 現状: 58件の壁

### なぜ58件しかないか
1. Meta APIトークンが無効（最大のブロッカー）
2. 手動クロールのみ（定期実行なし）
3. クロール対象キーワードが限定的

### なぜ2000件が必要か
- ジャンル別分析が意味を持つ: 最低10件/ジャンル × 20ジャンル = 200件
- ヒット判定の統計的有意性: 上位20% = 400件 → 全体2000件
- 検索の実用性: 検索して何も出ないUX → 最低数百件必要

---

## クロールソースの優先度

### Source 1: Meta Ad Library API (最優先)
**カバー**: Facebook, Instagram 広告
**メリット**:
- 公式API → データ品質高い
- 日本のD2C/EC広告が豊富
- snapshot_url → メディア抽出可能
**制約**:
- APIトークンが必要（ユーザーが取得）
- レートリミット: ~200 req/hour
- 1リクエストあたり最大25件
**取得見込み**: 1時間で ~5000件の広告IDを取得可能

### Source 2: Meta Ad Library Web (スクレイピング)
**カバー**: 同上
**メリット**: トークン不要
**制約**:
- Playwright でスクレイピング → 速度遅い
- 1ページ ~20件 × ページ送り → 1時間で ~200件
- IPブロックのリスク
**用途**: APIトークン取得前の緊急データ補充

### Source 3: YouTube Ads (将来)
**カバー**: YouTube 動画広告
**メリット**: 動画広告の宝庫
**制約**: 公式APIで広告データは取れない、スクレイピング必要
**コード状態**: `youtube_crawler.py` 存在するが未テスト

### Source 4: TikTok Creative Center
**カバー**: TikTok 広告
**メリット**: TikTok の成長市場
**コード状態**: `tiktok_crawler.py` 存在するが未テスト

### Source 5-10: その他
- X (Twitter) Ads: `x_twitter_crawler.py`
- Google Ads: `google_ads_crawler.py`
- LINE Ads: `line_crawler.py`
- Pinterest: `pinterest_crawler.py`
- SmartNews: `smartnews_crawler.py`
- Gunosy: `gunosy_crawler.py`

---

## 2000件達成プラン

### Phase 1: Meta API クロール (Day 1-3)

**前提**: ユーザーがMeta APIトークンを取得済み

```bash
# ジャンル別キーワードリスト
keywords=(
  # 美容・コスメ
  "美容液" "化粧水" "クレンジング" "美白" "シミ" "シワ" "エイジングケア"
  # 健康食品
  "サプリメント" "青汁" "酵素" "プロテイン" "乳酸菌" "ビタミン"
  # ダイエット
  "ダイエット" "痩せる" "糖質制限" "ファスティング" "置き換え"
  # 育毛・薄毛
  "育毛" "薄毛" "AGA" "発毛" "頭皮ケア"
  # スキンケア
  "日焼け止め" "保湿" "ニキビ" "毛穴" "洗顔"
  # 脱毛
  "脱毛" "除毛" "ムダ毛" "家庭用脱毛"
  # 転職・副業
  "転職" "副業" "フリーランス" "プログラミングスクール"
  # 投資・金融
  "投資" "FX" "仮想通貨" "NISA" "不動産投資"
  # 教育
  "英会話" "TOEIC" "資格" "オンライン学習"
  # EC・物販
  "通販" "定期購入" "初回限定" "お試し"
)

# 各キーワードで50件ずつクロール
for kw in "${keywords[@]}"; do
  curl -X POST "http://localhost:8000/api/v1/rankings/quick-crawl" \
    -H "Content-Type: application/json" \
    -d "{\"keyword\": \"$kw\", \"limit\": 50}"
  sleep 20  # レートリミット対策
done
```

**見込み**: 30キーワード × 50件 = 最大1500件（重複除外で~800-1000件）

### Phase 2: 広告主ベースクロール (Day 3-5)

Phase 1で見つかった広告主名で追加クロール:
```bash
# DB から広告主名を取得
python -c "
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from sqlalchemy import func
s = SyncSessionLocal()
advertisers = s.query(Ad.advertiser_name, func.count(Ad.id))\
  .group_by(Ad.advertiser_name)\
  .order_by(func.count(Ad.id).desc())\
  .limit(50).all()
for name, count in advertisers:
    print(f'{name}: {count}')
s.close()
"

# 上位広告主の全広告を取得
for advertiser in "株式会社A" "株式会社B" "株式会社C"; do
  curl -X POST "http://localhost:8000/api/v1/rankings/quick-crawl" \
    -H "Content-Type: application/json" \
    -d "{\"keyword\": \"$advertiser\", \"limit\": 100}"
  sleep 20
done
```

**見込み**: 追加 500-1000件

### Phase 3: Web スクレイピング補完 (Day 5-7)

Meta API で取れない広告をPlaywrightでスクレイピング:
```bash
# Meta Ad Library の検索ページを直接スクレイピング
# crawler_manager.py 経由
curl -X POST "http://localhost:8000/api/v1/ads/crawl" \
  -H "Content-Type: application/json" \
  -d '{
    "platform": "facebook",
    "search_term": "美容",
    "country": "JP",
    "limit": 100,
    "use_playwright": true
  }'
```

---

## クロール後のパイプライン

```
クロール完了
  ↓ (即座に)
classify_ads.py → ジャンル分類
fix_titles.py → タイトル正規化
fix_destination_urls.py → URL解決
  ↓ (バッチ)
collect_delivery_dates.py → 配信期間
check_ad_survival.py → 生存チェック
  ↓ (非同期/Worker)
extract_missing_videos.py → メディアURL
fix_bad_thumbnails.py → サムネイル
  ↓ (最後)
recompute_hit_scores.py → スコア計算
```

### 自動化（D7: Scheduled Crawl の実装）
```python
# cron ジョブ or Lambda スケジューラー
# 毎日 AM 3:00 に実行
# 1. 全キーワードでクロール（差分のみ）
# 2. 新規広告に全分析パイプライン実行
# 3. 既存広告の生存チェック
# 4. スコア再計算
```

---

## 重複排除

### 問題
同じ広告が異なるキーワードで複数回クロールされる

### 対策
- `ad_id` (Meta Ad Library ID) でユニーク制約
- INSERT 前に既存チェック
- `crawl_tasks.py` の `_merge_crawled_data()` で重複防止（D31で修正済み）

---

## クロール品質の監視

### メトリクス
```sql
-- 日別クロール数
SELECT DATE(created_at) as date, COUNT(*) as count
FROM ads GROUP BY DATE(created_at) ORDER BY date DESC LIMIT 7;

-- ジャンル分布
SELECT category, COUNT(*) FROM ads GROUP BY category ORDER BY COUNT(*) DESC;

-- データ完全性
SELECT
  COUNT(*) as total,
  COUNT(category) as has_category,
  COUNT(destination_url) as has_lp,
  COUNT(video_url) as has_video,
  COUNT(thumbnail_url) as has_thumb
FROM ads;
```

### 目標
| 日付 | 累計件数 | ジャンル数 |
|------|---------|-----------|
| Day 0 | 58 | ? |
| Day 1 | 200+ | 5+ |
| Day 3 | 500+ | 10+ |
| Day 5 | 1000+ | 15+ |
| Day 7 | 2000+ | 20+ |
