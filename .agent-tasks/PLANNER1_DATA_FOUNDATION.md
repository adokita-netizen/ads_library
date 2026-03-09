# Planner 1: DATA FOUNDATION
# 担当: Agent A (データ基盤) + Agent D (メディア・クロール)

## あなたの使命
**既存58件の広告データを完全に埋め、新しい広告を200件以上取り込む。**
コードは既に書かれている。あなたの仕事は「動かす」こと。

---

## 現状把握

### 既にあるもの（作り直し不要）
- ✅ Dockerfile.worker: Playwright + Chromium インストール済み (`docker/Dockerfile.worker` L57)
- ✅ MediaExtractor: HTTP + Playwright 2段階抽出 (`backend/app/services/media_extraction.py`)
- ✅ dispatcher.py: SQS heavy/light 振り分け済み
- ✅ 10個のクローラー: Meta/YouTube/TikTok/X/Google/LINE/Pinterest等
- ✅ ECS task definition: Playwright環境変数設定済み (`terraform/ecs.tf`)
- ✅ media_tasks.py: extract_media_task() 実装済み
- ✅ crawl_tasks.py: クロールタスク実装済み

### ブロッカー
- ❌ Meta APIトークン無効 → ユーザーが取得する必要あり
- ❌ 58件しか広告がない
- ❌ snapshot_urlのみ（実メディアURL無し）
- ⚠️ dispatcher.py のFIFOキュー MessageGroupId → 確認必要

---

## Phase 1: 即座にやること (Day 1)

### Task 1-1: dispatcher.py FIFO確認 [Agent D]
**ファイル**: `backend/app/tasks/dispatcher.py` L113-115
```python
if queue_url.endswith(".fifo"):
    send_kwargs["MessageGroupId"] = task_name
    send_kwargs["MessageDeduplicationId"] = message_id
```
- 本番SQSキューが `.fifo` かどうか確認
- `terraform/sqs.tf` を読んで実際のキュー名を確認
- FIFO でなければこのコードは実行されないので問題なし
- FIFO の場合、task_name ベースのグルーピングは意図通りか確認

### Task 1-2: 既存58件の全分析実行 [Agent A]
**目的**: 58件の広告の ad_metadata を完全に埋める

以下のスクリプトを順番に実行:
```bash
cd C:/Users/ishit/ads_library/backend

# 1. ジャンル分類
python -m scripts.classify_ads

# 2. タイトル修正
python -m scripts.fix_titles

# 3. 遷移先URL修正
python -m scripts.fix_destination_urls

# 4. 配信日付収集
python -m scripts.collect_delivery_dates

# 5. リアルメトリクス収集（Meta API必要 → トークン有効なら）
python -m scripts.collect_real_metrics

# 6. 広告生存チェック
python -m scripts.check_ad_survival
```

各スクリプト実行後、成功件数・失敗件数を記録。

### Task 1-3: メディアURL抽出テスト [Agent D]
**目的**: 1件の広告でメディア抽出パイプラインが動くか確認

```bash
cd C:/Users/ishit/ads_library/backend

# ローカルでテスト（Playwright使用）
python -c "
import asyncio
from app.services.media_extraction import MediaExtractor
extractor = MediaExtractor()
# 既存広告のsnapshot_urlを1件使ってテスト
result = asyncio.run(extractor.extract('https://www.facebook.com/ads/library/?id=XXXXX', use_playwright=True))
print(result)
"
```
- 動けば → バッチ実行へ進む
- 動かなければ → エラーを特定して修正

### Task 1-4: メディアバッチ抽出 [Agent D]
**ファイル**: `backend/scripts/extract_missing_videos.py`
```bash
cd C:/Users/ishit/ads_library/backend
python -m scripts.extract_missing_videos
```
- 88件の video_url=NULL を埋める
- 完了後、DBで video_url/image_url の埋まり具合を確認

---

## Phase 2: データ増量 (Day 2-3)

### Task 2-1: Meta APIトークン設定 [ユーザー依存]
- ユーザーがMeta Business APIからトークンを取得
- `settings` API経由 or DB直接で設定
- トークン有効性テスト: `/api/v1/ads/crawl` で少数クロール

### Task 2-2: 新規クロール実行 [Agent D]
```bash
# API経由でクロール実行
curl -X POST "http://localhost:8000/api/v1/rankings/quick-crawl" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "美容", "limit": 50}'

# 複数ジャンルで繰り返し
# 健康食品, ダイエット, 育毛, サプリメント, コスメ, 脱毛, etc.
```

### Task 2-3: クロール後の全分析パイプライン [Agent A]
新しく取り込んだ広告に対して Task 1-2 を再実行

### Task 2-4: サムネイル修復 [Agent D]
**ファイル**: `backend/scripts/fix_bad_thumbnails.py`
```bash
cd C:/Users/ishit/ads_library/backend
python -m scripts.fix_bad_thumbnails
```

---

## Phase 3: データ品質向上 (Day 4-5)

### Task 3-1: データヘルスレポート [Agent A]
DBに接続して以下を確認:
```sql
-- 基本統計
SELECT COUNT(*) as total,
       COUNT(video_url) as has_video,
       COUNT(image_url) as has_image,
       COUNT(thumbnail_url) as has_thumbnail,
       COUNT(destination_url) as has_lp,
       COUNT(CASE WHEN ad_metadata->>'latest_hit_score' IS NOT NULL THEN 1 END) as has_score
FROM ads;
```

### Task 3-2: ヒットスコア再計算 [Agent A → Agent C に依頼]
全広告のヒットスコアを最新データで再計算。
**注意**: `recompute_hit_scores.py` は Agent C の領域。
Planner 2 (Agent C 担当) に依頼すること。

### Task 3-3: メディアステータス更新 [Agent D]
**ファイル**: `backend/scripts/update_media_status.py`
全広告の `media_extraction_status` を最新状態に更新。

---

## ファイル所有権（厳守）

### Agent A が触れるファイル
```
backend/scripts/classify_ads.py
backend/scripts/fix_destination_urls.py
backend/scripts/fix_titles.py
backend/scripts/collect_delivery_dates.py
backend/scripts/collect_real_metrics.py
backend/scripts/check_ad_survival.py
backend/app/tasks/metrics_tasks.py
backend/app/models/ad.py (フィールド追加のみ)
backend/app/models/ad_metrics.py (フィールド追加のみ)
```

### Agent D が触れるファイル
```
backend/scripts/extract_missing_videos.py
backend/scripts/backfill_media_urls.py
backend/scripts/fix_bad_thumbnails.py
backend/scripts/update_media_status.py
backend/scripts/fix_creative_types.py
backend/app/services/media_extraction.py
backend/app/services/thumbnail_fetcher.py
backend/app/services/crawling/ (全ファイル)
backend/app/tasks/crawl_tasks.py
backend/app/tasks/media_tasks.py
docker/Dockerfile.worker
```

### 絶対触るな
```
frontend/                           ← Planner 3 (Agent B) の領域
backend/app/services/ranking/       ← Planner 2 (Agent C) の領域
backend/app/api/endpoints/rankings.py ← Planner 2 (Agent C) の領域
backend/app/services/competitive/   ← Planner 2 (Agent C) の領域
backend/app/services/prediction/    ← Planner 2 (Agent C) の領域
```

---

## コード品質改修（Agent A 未完了分）

### ★ CRITICAL: sqs_ecs_trigger.py — batchItemFailures未対応
**ファイル**: `backend/sqs_ecs_trigger.py`
- 現状: 失敗時も `{"results": results}` を返す → SQSがメッセージ削除 → タスク消失
- 修正: 失敗レコードを `batchItemFailures` で返す
```python
if failures:
    return {"batchItemFailures": [{"itemIdentifier": mid} for mid in failures]}
```

### ★ CRITICAL: lambda.tf — ReportBatchItemFailures未設定
**ファイル**: `terraform/lambda.tf`
- event_source_mapping に `function_response_types = ["ReportBatchItemFailures"]` 追加

### HIGH: lambda_handler.py — エラーレスポンスに str(e) 露出
- 本番では詳細エラーをマスクすべき（Internal server error のみ返す）

### MEDIUM: lambda_handler.py — _init_database() 毎回実行
- `_DB_INITIALIZED` フラグで2回目以降スキップ

---

## 完了基準

- [ ] 58件の既存広告: ad_metadata の主要フィールドが埋まっている
- [ ] video_url: 動画広告の80%以上で取得済み
- [ ] image_url/thumbnail_url: 全広告の90%以上で取得済み
- [ ] 新規クロール: 合計200件以上の広告がDBに存在
- [ ] メディア抽出パイプラインがE2Eで動作確認済み
- [ ] sqs_ecs_trigger.py: batchItemFailures対応済み
- [ ] lambda.tf: ReportBatchItemFailures設定済み

## 報告先
- `A/status.md` と `D/status.md` を更新
- クロスプランナー連絡: `.agent-tasks/COORDINATION_LOG.md` に記載
