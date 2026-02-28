# Agent C 大型タスク: 分析APIパイプライン構築

## 概要
ヒットスコアの内訳表示・広告主分析・スコア分布など、フロントエンドが必要とする分析データを返すAPIエンドポイント群を構築する。

## 必ず最初に読むファイル
```
backend/app/services/ranking/ranking_service.py     ← compute_hit_score() の現在の実装
backend/app/api/endpoints/rankings.py               ← 既存のAPI全体
backend/app/models/ad.py                            ← Adモデル
backend/app/models/ad_metrics.py                    ← AdDailyMetrics, ProductRanking
```

---

## タスク1: GET /rankings/score-breakdown/{ad_id}
**個別広告のスコア内訳を返すエンドポイント**

### レスポンス形式
```json
{
  "ad_id": 123,
  "product_name": "...",
  "advertiser_name": "...",
  "hit_score": 78.5,
  "hit_level": "mega_hit",
  "is_hit": true,
  "signals": {
    "longevity": {"score": 35.0, "max": 40, "detail": "配信日数: 95日"},
    "spend": {"score": 15.0, "max": 20, "detail": "推定消化額: 120,000円"},
    "active_bonus": {"score": 20.0, "max": 20, "detail": "配信中 + 60日以上"},
    "creative": {"score": 7.0, "max": 10, "detail": "動画あり + サムネイルあり"},
    "trend": {"score": 3.0, "max": 10, "detail": "メトリクスデータあり"}
  },
  "days_running": 95,
  "is_still_running": true,
  "estimated_spend_jpy": 120000,
  "first_seen_at": "2025-11-25T...",
  "last_seen_at": null
}
```

### 実装方針
- `compute_hit_score(ad, metrics, genre_stats)` を呼んで `signals` dictを取得
- signalsの各キーにmax値とdetail説明文を付与
- ad_metadataから推定値も含める

---

## タスク2: GET /rankings/score-distribution
**全広告のスコア分布データを返す**

### レスポンス形式
```json
{
  "total_ads": 176,
  "distribution": [
    {"range": "0-9", "count": 10},
    {"range": "10-19", "count": 26},
    {"range": "20-29", "count": 15},
    {"range": "30-39", "count": 11},
    {"range": "40-49", "count": 18},
    {"range": "50-59", "count": 12},
    {"range": "60-69", "count": 10},
    {"range": "70-79", "count": 7},
    {"range": "80-89", "count": 42},
    {"range": "90-100", "count": 25}
  ],
  "stats": {
    "mean": 56.4,
    "median": 53.0,
    "max": 93.0,
    "min": 12.1,
    "hit_count": 25,
    "mega_hit_count": 74,
    "still_running_count": 99
  },
  "by_genre": {
    "other": {"mean": 56.4, "count": 176, "hit_count": 25, "mega_hit_count": 74}
  }
}
```

### 実装方針
- 全Adを取得し ad_metadata.latest_hit_score でバケット化
- ジャンル別の統計も算出
- NumPy不要 — 純Pythonでmedian/mean計算

---

## タスク3: GET /rankings/advertiser-detail
**広告主の全広告を集約して分析する**

### パラメータ
- `advertiser_name: str` (必須)

### レスポンス形式
```json
{
  "advertiser_name": "XYZ Corp",
  "total_ads": 15,
  "active_ads": 8,
  "avg_hit_score": 67.3,
  "best_hit_score": 93.0,
  "total_estimated_spend_jpy": 1500000,
  "avg_days_running": 120,
  "hit_ads": [
    {
      "ad_id": 123,
      "product_name": "...",
      "hit_score": 93.0,
      "hit_level": "mega_hit",
      "days_running": 190,
      "is_still_running": true,
      "estimated_spend_jpy": 200000,
      "thumbnail": "..."
    }
  ],
  "non_hit_ads": [...]
}
```

### 実装方針
- `Ad.advertiser_name.ilike(f"%{name}%")` でフィルタ
- 各広告のad_metadataからスコアとメトリクスを取得
- hit/non-hitを分けてリスト化

---

## タスク4: GET /rankings/top-advertisers
**広告主別ランキング（広告主単位の集約）**

### パラメータ
- `limit: int = 20`
- `sort_by: str = "total_spend"` (total_spend | avg_score | ad_count)

### レスポンス形式
```json
{
  "advertisers": [
    {
      "advertiser_name": "XYZ Corp",
      "ad_count": 15,
      "active_ad_count": 8,
      "hit_ad_count": 5,
      "mega_hit_count": 3,
      "avg_hit_score": 67.3,
      "best_hit_score": 93.0,
      "total_estimated_spend_jpy": 1500000,
      "avg_days_running": 120
    }
  ]
}
```

### 実装方針
- `session.query(Ad).group_by(Ad.advertiser_name)` で集約
- ad_metadataからスコアを取得してPythonで集計

---

## タスク5: GET /rankings/longevity-analysis
**配信日数とスコアの相関分析**

### レスポンス形式
```json
{
  "scatter_data": [
    {"ad_id": 1, "days_running": 95, "hit_score": 78.5, "is_still_running": true, "estimated_spend": 120000},
    ...
  ],
  "buckets": [
    {"range": "1-14d", "count": 30, "avg_score": 15.2, "hit_rate": 0.0},
    {"range": "15-29d", "count": 20, "avg_score": 30.5, "hit_rate": 0.05},
    {"range": "30-59d", "count": 35, "avg_score": 52.0, "hit_rate": 0.4},
    {"range": "60-89d", "count": 27, "avg_score": 68.0, "hit_rate": 0.7},
    {"range": "90-119d", "count": 34, "avg_score": 75.0, "hit_rate": 0.85},
    {"range": "120d+", "count": 30, "avg_score": 85.0, "hit_rate": 0.95}
  ]
}
```

---

## コンフリクト防止ルール
- `INSTRUCTIONS.md` のルールを厳守
- 変更するファイル: `backend/app/api/endpoints/rankings.py`（エンドポイント追加）、`backend/app/services/ranking/ranking_service.py`（ヘルパー関数追加のみ）
- `frontend/` は一切触らない
- `backend/app/tasks/`, `backend/scripts/collect_*.py` は触らない
- 新規エンドポイントは既存の `router = APIRouter(prefix="/rankings")` に追加
- 日本語の print/log文は避け、英語で記述（cp932エンコーディング問題防止）

## 完了条件
- 5つのエンドポイントが全て動作すること
- 既存のエンドポイント（/products, /hit-ads, /genre-summary等）が壊れていないこと
- uvicorn起動時にインポートエラーがないこと
