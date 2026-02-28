# Agent C: 指示書

## あなたの役割
バックエンド・スコアリングエンジニア。
ヒット判定ロジックの精度向上・ランキングAPIの拡張を担当する。

## タスク一覧（上から順に実行）

### 済 ~~1. メディアURL補完~~
- 指示書: `C_メディアURL補完.md`
- スクリプト `backend/scripts/backfill_media_urls.py` は作成済み

### 済 ~~2. ヒット判定精度向上~~
### 済 ~~3. 分析APIパイプライン~~
### 済 ~~4. APIレスポンス統合~~

### 済 ~~5. トレンド分析 & ジャンル比較API~~

### 6. データ精度向上 & LP検証API ← 現在のタスク
- 指示書: `C6_データ精度向上API.md`
- LP到達性検証（check_lp_health.py + API）
- 広告品質サマリーAPI
- hit-adsにdestination_url確実含める

### ★ 依存関係
Agent A の「リアルメトリクス収集」が先に完了していると、
スコア計算の入力データ（audience_size, platforms, days_running等）の
品質が上がる。A未完了でも実行可能だが、A完了後に再実行推奨。

## 作業開始前に必ず読むファイル
```
backend/app/services/ranking/ranking_service.py            ← ★最重要: 現在のスコア計算
backend/app/services/competitive/trend_predictor.py        ← velocity/acceleration分析
backend/app/services/competitive/spend_estimator.py        ← CPM推定モデル
backend/app/services/prediction/performance_predictor.py   ← ML予測モデル
backend/app/services/prediction/fatigue_detector.py        ← 疲労検知
backend/app/services/prediction/feature_engineering.py     ← 31特徴量
backend/app/models/ad_metrics.py                           ← AdDailyMetrics, ProductRanking
backend/app/models/ad.py                                   ← Adモデル
backend/app/models/analysis.py                             ← AdAnalysis (winning_score等)
backend/app/api/endpoints/rankings.py                      ← ランキングAPI
```

---

## ★★★ コンフリクト防止ルール ★★★

### 触っていいファイル（Agent C の専有領域）
```
backend/app/services/ranking/ranking_service.py  ← 修正OK（スコア計算改善）
backend/app/services/ranking/__init__.py         ← 修正OK
backend/app/api/endpoints/rankings.py            ← 修正OK（API拡張）
backend/app/services/competitive/spend_estimator.py   ← 修正OK
backend/app/services/competitive/trend_predictor.py   ← 修正OK
backend/app/services/prediction/                      ← 修正OK
backend/app/models/ad_metrics.py                      ← フィールド追加OK（既存削除NG）
backend/app/models/analysis.py                        ← フィールド追加OK（既存削除NG）
backend/scripts/recompute_hit_scores.py               ← 新規作成OK
backend/scripts/check_lp_health.py                   ← 新規作成OK（C6: LP検証スクリプト）
backend/app/schemas/                                  ← レスポンススキーマ修正OK
```

### 絶対に触ってはいけないファイル
```
# Agent A の領域（データ収集・クローリング）
backend/scripts/collect_real_metrics.py     ← 触るな
backend/scripts/extract_missing_videos.py   ← 触るな
backend/scripts/check_ad_survival.py        ← 触るな
backend/scripts/fix_bad_thumbnails.py       ← 触るな
backend/scripts/backfill_media_urls.py      ← 触るな
backend/app/tasks/                          ← 触るな
backend/app/services/crawling/              ← 触るな
backend/app/services/media_extraction.py    ← 触るな
backend/app/services/thumbnail_fetcher.py   ← 触るな

# Agent B の領域（フロントエンド）
frontend/                                   ← 一切触るな
```

### ad_metadata を更新する場合の注意
```python
# 必ずこのパターンで更新する
meta = dict(ad.ad_metadata or {})
meta["latest_hit_score"] = hit_score
meta["latest_score_breakdown"] = signals
ad.ad_metadata = meta
flag_modified(ad, "ad_metadata")
session.commit()

# ★ Agent Aが書き込んだキーを削除・上書きしない
# Agent A のキー: estimated_audience_min, estimated_audience_max,
#                publisher_platforms, delivery_start_time, delivery_stop_time,
#                is_still_running, estimation_method, impressions_from_audience
# → これらは読み取りのみ。上書き厳禁。
```

### ProductRanking テーブルへの書き込み
```python
# Agent C のみが ProductRanking に書き込む
# hit_score, trend_score, is_hit, rank の更新は Agent C の責任
# 他のエージェントは ProductRanking を読み取り専用で使用
```

## 作業ディレクトリ
必ず `cd C:/Users/ishit/ads_library/backend` から実行すること。

## 完了報告
作業が終わったら `C/status.md` を作成してステータスを記録すること。
