# エラー復旧視点 — 失敗した時に何が起きるか、どう回復するか

## 原則
**サイレント失敗が最も危険。** 失敗が見えないと、データが欠損しているのに気づかない。

---

## パターン 1: クロール失敗

### 症状
- 新しい広告がDBに入らない
- `/rankings/fresh-ads` が空

### 原因と対策

| 原因 | 検知方法 | 復旧方法 |
|------|---------|---------|
| Meta APIトークン期限切れ | 401レスポンス | ユーザーがトークン再取得 |
| Meta APIレートリミット | 429レスポンス | 待機して再実行（meta_crawler.py に実装済み）|
| ネットワークエラー | ConnectionError | NAT Instance確認、リトライ |
| クロール結果0件 | crawl_jobs テーブル確認 | キーワード変更して再実行 |
| dispatcher.py SQS送信失敗 | CloudWatch Logs | キュー設定確認 |

### 復旧コマンド
```bash
# クロールジョブの状態確認
curl "http://localhost:8000/api/v1/rankings/crawl-status" | python -m json.tool

# 手動クロール
curl -X POST "http://localhost:8000/api/v1/rankings/quick-crawl" \
  -H "Content-Type: application/json" \
  -d '{"keyword": "美容", "limit": 20}'
```

---

## パターン 2: メディア抽出失敗

### 症状
- thumbnail_url / image_url / video_url が NULL のまま
- 画面のサムネイルが壊れている

### 原因と対策

| 原因 | 検知方法 | 復旧方法 |
|------|---------|---------|
| Playwright タイムアウト | media_extraction_status=failed | セマフォ数削減、タイムアウト延長 |
| Chromium クラッシュ | OOM in ECS | メモリ増加 (shm_size: 2048) |
| snapshot_url が無効 | 404/403 | snapshot_url 更新（再クロール）|
| S3 アップロード失敗 | boto3 exception | IAM ロール確認、バケット確認 |
| Worker 起動しない | ECS タスク失敗 | ECR イメージ確認、タスク定義確認 |

### 復旧コマンド
```bash
# 抽出失敗の広告を確認
cd C:/Users/ishit/ads_library/backend
python -c "
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
s = SyncSessionLocal()
failed = s.query(Ad).filter(Ad.media_extraction_status == 'failed').count()
null_video = s.query(Ad).filter(Ad.video_url == None, Ad.creative_type == 'video').count()
print(f'Failed: {failed}, Missing video: {null_video}')
s.close()
"

# 失敗した広告のメディア再抽出
python -m scripts.extract_missing_videos
```

---

## パターン 3: スコア計算失敗

### 症状
- hit_score が全部0 or NULL
- HITバッジが表示されない
- ランキング順位が不正

### 原因と対策

| 原因 | 検知方法 | 復旧方法 |
|------|---------|---------|
| 入力データ不足 | ad_metadata が空 | Agent A のスクリプト実行が先 |
| product_rankings テーブルが空 | SELECT COUNT(*) | recompute_hit_scores 再実行 |
| スコア閾値が不適切 | 全員がHIT or 誰もHITでない | ranking_service.py の閾値調整 |
| ad_metadata の flag_modified 忘れ | DBのad_metadataが古い | flag_modified パターン確認 |

### 復旧コマンド
```bash
cd C:/Users/ishit/ads_library/backend

# スコア再計算
python -m scripts.recompute_hit_scores

# 確認
python -c "
from app.core.database import SyncSessionLocal
from app.models.ad_metrics import ProductRanking
s = SyncSessionLocal()
count = s.query(ProductRanking).count()
hits = s.query(ProductRanking).filter(ProductRanking.is_hit == True).count()
print(f'Total rankings: {count}, Hits: {hits}')
s.close()
"
```

---

## パターン 4: API 500エラー

### 症状
- フロントに「エラーが発生しました」表示
- ネットワークタブで 500 Internal Server Error

### 原因と対策

| 原因 | 検知方法 | 復旧方法 |
|------|---------|---------|
| DB接続エラー | "connection refused" in logs | RDS起動確認、SG確認 |
| NoneType エラー | traceback in logs | データの NULL チェック追加 |
| メモリ不足 (Lambda) | "Runtime exited" | Lambda メモリ増加 |
| タイムアウト (Lambda) | "Task timed out" | タイムアウト延長 or クエリ最適化 |
| import エラー | "ModuleNotFoundError" | requirements.txt 確認 |

### デバッグ手順
```bash
# Lambda ログ確認
aws logs tail /aws/lambda/vaap-production-api --since 30m --format short | grep ERROR

# ローカルで再現
cd C:/Users/ishit/ads_library/backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 問題のエンドポイントを直接叩く
curl -v "http://localhost:8000/api/v1/rankings/pro-ranking?page=1"
```

---

## パターン 5: フロント表示崩れ

### 症状
- 白画面
- 無限ローディング
- レイアウト崩れ

### 原因と対策

| 原因 | 検知方法 | 復旧方法 |
|------|---------|---------|
| JSエラー | DevTools Console | エラー箇所を修正 |
| APIレスポンス形式変更 | undefined is not... | 型チェック追加 |
| 画像 403/404 | ネットワークタブ | フォールバック確認 |
| CORSエラー | "blocked by CORS policy" | backend CORS設定修正 |
| SSR/CSR ミスマッチ | Hydration error | dynamic import確認 |

### デバッグ手順
```bash
# ビルド確認
cd C:/Users/ishit/ads_library/frontend
npx next build --no-lint

# 開発モードで起動
npm run dev

# DevTools Console を確認
# Network タブで Failed requests を確認
```

---

## パターン 6: SQS メッセージ消失

### 症状
- クロール/メディア抽出タスクが実行されない
- SQSキューが空なのにタスクが完了していない

### 原因: batchItemFailures 未対応（現在の既知バグ）

```
現在のフロー:
1. SQS → Lambda trigger → ECS タスク起動
2. ECS タスク失敗
3. Lambda は "成功" を返す ← ★ バグ
4. SQS がメッセージを削除
5. タスクは永久に失われる

修正後のフロー:
1. SQS → Lambda trigger → ECS タスク起動
2. ECS タスク失敗
3. Lambda は batchItemFailures を返す ← 修正
4. SQS がメッセージをキューに戻す
5. リトライされる（最大3回）
6. 3回失敗 → DLQ に移動
```

### 確認コマンド
```bash
# DLQ にメッセージが溜まっていないか
aws sqs get-queue-attributes \
  --queue-url https://sqs.ap-northeast-1.amazonaws.com/271669411511/vaap-production-heavy-tasks-dlq \
  --attribute-names ApproximateNumberOfMessages
```

---

## パターン 7: データ不整合

### 症状
- product_rankings と ad_metadata.latest_hit_score が違う
- ジャンルサイドバーの件数と実際の件数が違う
- PRO DATABASE の順位がおかしい

### 復旧手順（全リセット）
```bash
cd C:/Users/ishit/ads_library/backend

# 1. ジャンル再分類
python -m scripts.classify_ads

# 2. メトリクス再収集（可能なら）
python -m scripts.collect_delivery_dates

# 3. スコア再計算
python -m scripts.recompute_hit_scores

# 4. 確認
python -c "
from app.core.database import SyncSessionLocal
from app.models.ad import Ad
from app.models.ad_metrics import ProductRanking
s = SyncSessionLocal()
ads = s.query(Ad).count()
ranked = s.query(ProductRanking).count()
print(f'Ads: {ads}, Ranked: {ranked}, Gap: {ads - ranked}')
s.close()
"
```

---

## エラー検知の自動化（将来）

```python
# 日次ヘルスチェックスクリプト
def daily_health_check():
    checks = {
        "api_health": check_api_health(),
        "db_connection": check_db(),
        "data_freshness": check_latest_crawl_date(),
        "media_coverage": check_media_url_ratio(),
        "score_coverage": check_score_coverage(),
        "thumbnail_errors": check_thumbnail_403_rate(),
        "dlq_messages": check_dlq_depth(),
    }

    failures = {k: v for k, v in checks.items() if not v["ok"]}
    if failures:
        send_alert(failures)  # Slack/Email
```
