# Agent D: 指示書

## あなたの役割
バックエンド・メディアエンジニア。
動画URL抽出・サムネイル品質改善・メディア補完・クローリングサービスを担当する。

## タスク一覧（上から順に実行）

### 1. メディア品質パイプライン ← 現在のタスク
- 指示書: `D1_メディア品質パイプライン.md`
- 動画URL抽出（88件 video_url=NULL）
- サムネイル品質改善
- image_url/video_url 補完

## 作業開始前に必ず読むファイル
```
backend/scripts/extract_missing_videos.py   ← 動画URL抽出
backend/scripts/backfill_media_urls.py      ← メディアURL補完
backend/scripts/fix_bad_thumbnails.py       ← サムネイル品質修復
backend/app/services/media_extraction.py    ← MediaExtractor
backend/app/services/thumbnail_fetcher.py   ← ThumbnailFetcher
backend/app/services/crawling/              ← クローラー群
backend/app/tasks/crawl_tasks.py            ← クロールタスク
backend/app/tasks/media_tasks.py            ← メディア抽出タスク
backend/app/models/ad.py                    ← Adモデル（メディアフィールド参照）
```

---

## ★★★ コンフリクト防止ルール ★★★

### 触っていいファイル（Agent D の専有領域）
```
backend/scripts/extract_missing_videos.py   ← 修正・実行OK
backend/scripts/backfill_media_urls.py      ← 修正・実行OK
backend/scripts/fix_bad_thumbnails.py       ← 修正・実行OK
backend/app/services/media_extraction.py    ← 修正OK
backend/app/services/thumbnail_fetcher.py   ← 修正OK
backend/app/services/crawling/              ← 全ファイル修正OK
backend/app/tasks/crawl_tasks.py            ← 修正OK
backend/app/tasks/media_tasks.py            ← 修正OK
```

### 絶対に触ってはいけないファイル
```
# Agent A の領域（データ品質・メトリクス）
backend/scripts/classify_ads.py             ← 触るな
backend/scripts/fix_destination_urls.py     ← 触るな
backend/scripts/fix_titles.py              ← 触るな
backend/scripts/collect_delivery_dates.py   ← 触るな
backend/scripts/collect_real_metrics.py     ← 触るな
backend/scripts/check_ad_survival.py        ← 触るな
backend/app/tasks/metrics_tasks.py          ← 触るな

# Agent B の領域（フロントエンド）
frontend/                                   ← 一切触るな

# Agent C の領域（スコアリング・ランキングAPI）
backend/app/services/ranking/               ← 触るな
backend/app/api/endpoints/rankings.py       ← 触るな
backend/app/services/competitive/           ← 触るな
backend/app/services/prediction/            ← 触るな
backend/scripts/recompute_hit_scores.py     ← 触るな
backend/scripts/check_lp_health.py         ← 触るな（Agent C の C6 タスク）
```

### Ad モデルの書き込みルール
Agent D が書き込んでよいカラム:
```
ad.video_url                  ← 動画URL
ad.image_url                  ← 画像URL
ad.thumbnail_url              ← サムネイルURL
ad.thumbnail_s3_key           ← S3サムネイル
ad.image_s3_key               ← S3画像
ad.image_s3_keys              ← カルーセル画像
ad.creative_type              ← video/image/carousel
ad.media_extraction_status    ← pending/completed/failed
ad.duration_seconds           ← 動画長
ad.resolution_width/height    ← 解像度
ad.file_size_bytes            ← ファイルサイズ
```

Agent D が書き込んでよい ad_metadata キー:
```python
meta["thumbnail_fixed"] = True
meta["creative_quality"] = "high"
meta["extraction_method"] = "playwright"
meta["media_urls_backfilled"] = True
```

Agent D が絶対に書き換えてはいけない ad_metadata キー:
```
days_running                  ← Agent A
is_still_running              ← Agent A
estimated_*                   ← Agent A
latest_hit_score              ← Agent C
hit_level                     ← Agent C
is_hit                        ← Agent C
latest_score_breakdown        ← Agent C
```

### ad_metadata 更新パターン（必須）
```python
from sqlalchemy.orm.attributes import flag_modified

meta = dict(ad.ad_metadata or {})
meta["your_key"] = "your_value"
ad.ad_metadata = meta
flag_modified(ad, "ad_metadata")
session.commit()
```

### cp932 エンコーディング対策
- print文は英語のみ
- NG: `print("動画抽出完了")`
- OK: `print("Video extraction complete")`
