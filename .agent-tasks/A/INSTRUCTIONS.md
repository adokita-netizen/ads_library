# Agent A: 指示書

## あなたの役割
バックエンド・データ基盤エンジニア。
広告データの収集・補完・品質向上を担当する。

## タスク一覧（上から順に実行）

### 済 ~~1. サムネイル品質修復~~
- 指示書: `A_サムネイル品質修復.md`
- スクリプト `backend/scripts/fix_bad_thumbnails.py` は作成・実行済み

### 済 ~~2. リアルメトリクス収集パイプライン~~

### 済 ~~3. データ品質パイプライン~~

### 4. データ鮮度管理 & エクスポート ← 現在のタスク
- 指示書: `A4_データ鮮度とエクスポート.md`
- 広告生存チェック改善
- CSVエクスポート
- データヘルスレポート

## 作業開始前に必ず読むファイル
```
backend/app/models/ad.py                        ← Adモデル定義
backend/app/models/ad_metrics.py                ← AdDailyMetrics定義
backend/app/core/database.py                    ← SyncSessionLocal (153行目)
backend/app/api/endpoints/settings.py           ← load_api_keys_from_db (444行目)
backend/app/services/crawling/meta_crawler.py   ← _estimate_ad_metrics関数
backend/app/tasks/metrics_tasks.py              ← メトリクス収集タスク
backend/app/services/media_extraction.py        ← MediaExtractor
```

---

## ★★★ コンフリクト防止ルール ★★★

### 触っていいファイル（Agent A の専有領域）
```
backend/scripts/collect_real_metrics.py     ← 新規作成OK
backend/scripts/check_ad_survival.py        ← 新規作成OK
backend/scripts/classify_ads.py             ← 修正OK
backend/scripts/fix_destination_urls.py     ← 修正OK
backend/scripts/fix_titles.py              ← 修正OK
backend/scripts/collect_delivery_dates.py   ← 修正OK
backend/scripts/recompute_hit_scores.py     ← 修正OK
backend/app/tasks/metrics_tasks.py          ← 修正OK
backend/app/models/ad.py                    ← フィールド追加OK（既存削除NG）
backend/app/models/ad_metrics.py            ← フィールド追加OK（既存削除NG）
```

### 絶対に触ってはいけないファイル
```
# Agent D の領域（メディア・クローリング）
backend/scripts/extract_missing_videos.py   ← 触るな
backend/scripts/backfill_media_urls.py      ← 触るな
backend/scripts/fix_bad_thumbnails.py       ← 触るな
backend/app/services/media_extraction.py    ← 触るな
backend/app/services/thumbnail_fetcher.py   ← 触るな
backend/app/services/crawling/              ← 触るな
backend/app/tasks/crawl_tasks.py            ← 触るな
backend/app/tasks/media_tasks.py            ← 触るな

# Agent C の領域（スコアリング）
backend/app/services/ranking/               ← 触るな
backend/app/api/endpoints/rankings.py       ← 触るな
backend/app/services/competitive/spend_estimator.py  ← 触るな
backend/app/services/competitive/trend_predictor.py  ← 触るな
backend/app/services/prediction/            ← 触るな
backend/scripts/check_lp_health.py         ← 触るな（Agent C の C6 タスク）
backend/scripts/recompute_hit_scores.py    ← 触るな

# Agent B の領域（フロントエンド）
frontend/                                   ← 一切触るな
```

### ad_metadata を更新する場合の注意
```python
# 必ずこのパターンで更新する
meta = dict(ad.ad_metadata or {})
meta["your_key"] = "your_value"
ad.ad_metadata = meta
flag_modified(ad, "ad_metadata")
session.commit()
```

## 作業ディレクトリ
必ず `cd C:/Users/ishit/ads_library/backend` から実行すること。

## 完了報告
作業が終わったら `A/status.md` にステータスを記録すること。
