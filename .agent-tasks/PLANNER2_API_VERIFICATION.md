# Planner 2: API VERIFICATION & QUALITY
# 担当: Agent C (スコアリング・ランキングAPI)

## あなたの使命
**105+のAPIエンドポイントが実データで正しく動くことを保証する。**
新しいエンドポイントは作らない。既存を「検証・修正・磨く」。

---

## 現状把握

### 既にあるもの（膨大）
- ✅ rankings.py: 14,779行、105+エンドポイント
- ✅ /pro-ranking: 23パラメータ対応の本格実装
- ✅ /dashboard-summary: 7つのKPIメトリクス計算
- ✅ /genre-master: 階層的ジャンル分類
- ✅ /hit-ads: 動的閾値でヒット判定
- ✅ /smart-autocomplete: ジャンル/商材/広告主サジェスト
- ✅ /search-collections: 検索条件保存・読込
- ✅ export系: CSV/JSON/レポート 3種
- ✅ competitive/, lp_analysis/, predictions/ 他12ルーターモジュール

### 問題
- エンドポイントは存在するが、58件の貧弱データで正しく動くか未検証
- エラーハンドリングが甘い箇所がある可能性
- フロントエンドが期待するレスポンス形式と実際のレスポンスにズレがある可能性

---

## Phase 1: スモークテスト (Day 1)

### Task 1-1: コアAPIのE2Eテスト

バックエンドを起動して、以下のエンドポイントを順番に叩く。
レスポンスの status code、レスポンス形式、データの妥当性を確認。

```bash
cd C:/Users/ishit/ads_library/backend

# バックエンド起動（別ターミナルで）
# uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# === Priority 1: PRO DATABASE に必要なAPI ===

# 1. ヘルスチェック
curl http://localhost:8000/api/health

# 2. ジャンルマスター（サイドバーのジャンル一覧）
curl "http://localhost:8000/api/v1/rankings/genre-master" | python -m json.tool | head -50

# 3. PRO RANKING（メインテーブル）
curl "http://localhost:8000/api/v1/rankings/pro-ranking?page=1&per_page=20" | python -m json.tool | head -100

# 4. ダッシュボードサマリー（KPIカード）
curl "http://localhost:8000/api/v1/rankings/dashboard-summary" | python -m json.tool

# 5. ヒット広告
curl "http://localhost:8000/api/v1/rankings/hit-ads?genre=all&limit=20" | python -m json.tool | head -100

# 6. オートコンプリート
curl "http://localhost:8000/api/v1/rankings/smart-autocomplete?query=美容" | python -m json.tool

# 7. スコア分布
curl "http://localhost:8000/api/v1/rankings/score-distribution" | python -m json.tool

# 8. ジャンル比較
curl "http://localhost:8000/api/v1/rankings/genre-comparison" | python -m json.tool
```

### Task 1-2: レスポンス形式チェック

PRO DATABASE のフロントエンド (`ProRankingTable.tsx`) が期待するフィールドを確認:
```
rank, management_id, thumbnail_url, product_name, advertiser_name,
genre, platform, view_increase, total_views, spend_increase,
total_spend, like_increase, days_running, hit_score, hit_level,
is_still_running, duration_seconds, destination_url, creative_type
```

`/pro-ranking` のレスポンスにこれらが全て含まれているか確認。
欠けていたら追加。型が違ったら修正。

### Task 1-3: エラーレスポンスの確認

```bash
# 存在しない広告ID
curl "http://localhost:8000/api/v1/rankings/score-breakdown/99999"

# 空のジャンル
curl "http://localhost:8000/api/v1/rankings/pro-ranking?genre=nonexistent"

# 不正なパラメータ
curl "http://localhost:8000/api/v1/rankings/pro-ranking?page=-1"
```

500エラーが返る場合は修正。適切な404/400が返るべき。

---

## Phase 2: データ品質API (Day 2-3)

### Task 2-1: ヒットスコア再計算
```bash
cd C:/Users/ishit/ads_library/backend

# Planner 1 がデータを埋めた後に実行
python -m scripts.recompute_hit_scores
```

### Task 2-2: LP検証スクリプト作成・実行
**ファイル**: `backend/scripts/check_lp_health.py` (C6タスク)
```bash
# 全広告のdestination_urlに対してHTTP HEAD/GETを実行
# レスポンスコードをad_metadata.lp_statusに記録
# 200=alive, 301/302=redirect, 404=dead, timeout=unreachable
```

### Task 2-3: スコアブレイクダウン検証
```bash
# 各広告のスコア内訳が妥当か確認
curl "http://localhost:8000/api/v1/rankings/score-breakdown/{ad_id}" | python -m json.tool

# 5シグナル（配信継続力/消化額/配信中ボーナス/クリエイティブ/トレンド）が
# 全てゼロでないことを確認
```

---

## Phase 3: セカンダリAPI検証 (Day 4-5)

### Task 3-1: 分析系APIテスト
```bash
# トレンド
curl "http://localhost:8000/api/v1/rankings/trends/weekly" | python -m json.tool

# 広告主詳細
curl "http://localhost:8000/api/v1/rankings/advertiser-detail?advertiser_name=XXX" | python -m json.tool

# クリエイティブDNA
curl "http://localhost:8000/api/v1/rankings/creative-dna/{ad_id}" | python -m json.tool

# ヒットファクター
curl "http://localhost:8000/api/v1/rankings/hit-factors" | python -m json.tool

# 勝ちパターン
curl "http://localhost:8000/api/v1/rankings/genre-winning-patterns?genre=美容" | python -m json.tool
```

### Task 3-2: エクスポート機能テスト
```bash
# CSV
curl "http://localhost:8000/api/v1/rankings/export/csv?genre=all" -o test_export.csv
# 中身確認
head -5 test_export.csv

# JSON
curl "http://localhost:8000/api/v1/rankings/export/json?genre=all" -o test_export.json
python -m json.tool test_export.json | head -50
```

### Task 3-3: 他のルーターモジュール検証
```bash
# Competitive Intelligence
curl "http://localhost:8000/api/v1/competitive/" | python -m json.tool

# LP Analysis
curl "http://localhost:8000/api/v1/lp-analysis/" | python -m json.tool

# Predictions
curl "http://localhost:8000/api/v1/predictions/" | python -m json.tool

# Media
curl "http://localhost:8000/api/v1/media/stats" | python -m json.tool
```

---

## ファイル所有権（厳守）

### Agent C が触れるファイル
```
backend/app/services/ranking/ranking_service.py
backend/app/services/ranking/__init__.py
backend/app/api/endpoints/rankings.py
backend/app/services/competitive/spend_estimator.py
backend/app/services/competitive/trend_predictor.py
backend/app/services/prediction/
backend/app/models/ad_metrics.py (フィールド追加のみ)
backend/app/models/analysis.py (フィールド追加のみ)
backend/scripts/recompute_hit_scores.py
backend/scripts/check_lp_health.py (新規作成OK)
backend/app/schemas/ (レスポンススキーマ修正OK)
```

### 絶対触るな
```
frontend/                              ← Planner 3 (Agent B) の領域
backend/scripts/classify_ads.py        ← Planner 1 (Agent A) の領域
backend/scripts/fix_*.py               ← Planner 1 (Agent A/D) の領域
backend/scripts/collect_*.py           ← Planner 1 (Agent A) の領域
backend/scripts/extract_*.py           ← Planner 1 (Agent D) の領域
backend/scripts/backfill_*.py          ← Planner 1 (Agent D) の領域
backend/app/services/crawling/         ← Planner 1 (Agent D) の領域
backend/app/services/media_extraction.py ← Planner 1 (Agent D) の領域
backend/app/tasks/crawl_tasks.py       ← Planner 1 (Agent D) の領域
backend/app/tasks/media_tasks.py       ← Planner 1 (Agent D) の領域
```

---

## 発見したバグ・問題の報告方法

1. **フロントに影響するAPI変更** → `COORDINATION_LOG.md` に記載してPlanner 3に通知
2. **データに関する問題** → `COORDINATION_LOG.md` に記載してPlanner 1に通知
3. **自分で修正した場合** → `C/status.md` を更新

---

## 完了基準

- [ ] /pro-ranking: 正しいデータがフロントエンドの期待形式で返る
- [ ] /dashboard-summary: KPI数値が実データを反映
- [ ] /hit-ads: ヒット判定が妥当（上位10-20%がHIT）
- [ ] /genre-master: ジャンル一覧と件数が正確
- [ ] /smart-autocomplete: 日本語検索が動作
- [ ] export系: CSV/JSONが正常にダウンロード可能
- [ ] 500エラーを返すエンドポイントが0件
- [ ] 全58件の広告がスコア付きで返される

## 報告先
- `C/status.md` を更新
- クロスプランナー連絡: `.agent-tasks/COORDINATION_LOG.md` に記載
