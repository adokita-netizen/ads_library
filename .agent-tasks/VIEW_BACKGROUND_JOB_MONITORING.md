# バックグラウンドジョブ監視視点 — 非同期処理の可視化と管理

## なぜ重要か

VEAPには多数のバックグラウンドジョブが存在:
- クロールジョブ（Meta API → DB）
- メディア抽出ジョブ（Playwright → 動画/画像URL抽出）
- スコア計算ジョブ（ranking_service → hit_score 更新）
- サムネイル取得ジョブ
- LP分析ジョブ
- AI生成ジョブ

これらが「実行中か」「成功したか」「失敗したか」が見えないのが現状の大きな問題。

---

## 現状のジョブ実行フロー

```
Lambda (API)
  ↓ SQS メッセージ送信
SQS (heavy-queue / light-queue)
  ↓ Worker がポーリング
ECS Worker (dispatcher.py)
  ↓ action 振り分け
各タスクハンドラー
  ├── crawl_tasks.py
  ├── media_tasks.py
  ├── media_extraction.py
  └── meta_crawler.py
```

### 現状の問題
```
1. ジョブの状態が見えない
   → APIリクエスト後に「処理中」だけ、完了通知なし

2. 失敗の把握が遅い
   → CloudWatch Logs を手動確認する必要がある

3. リトライの制御が不明
   → SQS の maxReceiveCount でDLQ送り
   → リトライ回数や間隔が可視化されていない

4. ジョブの優先度制御がない
   → FIFO キューだが優先度なし
```

---

## ジョブ管理テーブル設計

### jobs テーブル

```sql
CREATE TABLE jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50) NOT NULL,      -- 'crawl', 'media_extract', 'score_calc'
    status VARCHAR(20) NOT NULL DEFAULT 'pending',
    -- pending → queued → running → completed / failed / cancelled
    priority INTEGER DEFAULT 0,     -- 0=normal, 1=high, -1=low

    -- 入力パラメータ
    payload JSONB NOT NULL DEFAULT '{}',

    -- 実行情報
    sqs_message_id VARCHAR(100),
    worker_id VARCHAR(100),         -- ECSタスクID
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    duration_seconds NUMERIC,

    -- 結果
    result JSONB,                   -- 成功時の結果データ
    error_message TEXT,             -- 失敗時のエラー
    error_traceback TEXT,           -- スタックトレース
    retry_count INTEGER DEFAULT 0,
    max_retries INTEGER DEFAULT 3,

    -- 関連
    parent_job_id UUID REFERENCES jobs(id),  -- 親ジョブ
    ad_id UUID,                     -- 関連広告

    -- メタ
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_jobs_status ON jobs (status);
CREATE INDEX idx_jobs_type ON jobs (type, created_at DESC);
CREATE INDEX idx_jobs_ad ON jobs (ad_id);
```

### ジョブステータスの遷移

```
pending     → API がジョブを作成
  ↓
queued      → SQS にメッセージ送信完了
  ↓
running     → Worker がメッセージを取得、処理開始
  ↓
completed   → 正常完了
  or
failed      → エラー発生（リトライ上限内ならretry_count++、再度queued）
  or
cancelled   → ユーザーがキャンセル
  or
dead_letter → リトライ上限超過、DLQ送り
```

---

## ジョブ作成の改善

### 現状

```python
# rankings.py から直接 SQS 送信
sqs.send_message(
    QueueUrl=queue_url,
    MessageBody=json.dumps({"action": "crawl", "keyword": "美容"}),
    MessageGroupId="crawl"
)
# → ジョブIDなし、追跡不可能
```

### 改善後

```python
# app/services/job_service.py

class JobService:
    def __init__(self, db: Session):
        self.db = db

    def create_job(self, type: str, payload: dict,
                   priority: int = 0, ad_id: str = None) -> Job:
        job = Job(
            type=type,
            payload=payload,
            priority=priority,
            ad_id=ad_id,
            status="pending",
        )
        self.db.add(job)
        self.db.flush()  # IDを取得

        # SQS に送信
        message_id = send_to_sqs(
            action=type,
            payload={**payload, "job_id": str(job.id)},
        )

        job.status = "queued"
        job.sqs_message_id = message_id
        self.db.commit()

        return job

    def update_job_status(self, job_id: str, status: str,
                          result: dict = None, error: str = None):
        job = self.db.query(Job).get(job_id)
        job.status = status
        if status == "running":
            job.started_at = datetime.utcnow()
        if status in ("completed", "failed"):
            job.completed_at = datetime.utcnow()
            job.duration_seconds = (
                job.completed_at - job.started_at
            ).total_seconds()
        if result:
            job.result = result
        if error:
            job.error_message = error
            job.retry_count += 1
        self.db.commit()

# 使用例
job_service = JobService(db)
job = job_service.create_job(
    type="crawl",
    payload={"keyword": "美容", "limit": 25},
)
# return {"job_id": job.id, "status": "queued"}
```

### Worker側の更新

```python
# dispatcher.py の改善

async def process_message(message):
    job_id = message.get("job_id")

    if job_id:
        update_job_status(job_id, "running")

    try:
        result = await execute_action(message)
        if job_id:
            update_job_status(job_id, "completed", result=result)
    except Exception as e:
        if job_id:
            update_job_status(job_id, "failed", error=str(e))
        raise
```

---

## ジョブ監視API

### エンドポイント

```
GET  /api/v1/jobs                  → ジョブ一覧
GET  /api/v1/jobs/{id}             → ジョブ詳細
GET  /api/v1/jobs/{id}/logs        → ジョブログ
POST /api/v1/jobs/{id}/cancel      → キャンセル
POST /api/v1/jobs/{id}/retry       → 再実行
GET  /api/v1/jobs/stats            → 統計情報
GET  /api/v1/jobs/active           → 実行中ジョブ
```

### 統計レスポンス

```json
GET /api/v1/jobs/stats

{
  "total": 1234,
  "by_status": {
    "pending": 2,
    "queued": 5,
    "running": 3,
    "completed": 1200,
    "failed": 24
  },
  "by_type": {
    "crawl": {"total": 500, "success_rate": 0.95},
    "media_extract": {"total": 400, "success_rate": 0.88},
    "score_calc": {"total": 334, "success_rate": 0.99}
  },
  "last_24h": {
    "total": 45,
    "completed": 40,
    "failed": 5,
    "avg_duration_seconds": 32
  },
  "queue_depth": {
    "heavy": 5,
    "light": 2
  }
}
```

---

## フロントエンド: ジョブモニター画面

### 設定画面にタブ追加

```
設定 → ジョブ管理

┌─────────────────────────────────────────────────┐
│ ジョブ管理                                        │
├─────────┬─────────┬──────────┬──────────┬────────┤
│ 全て     │ 実行中(3) │ 完了(40) │ 失敗(5)  │ キュー(7) │
├─────────────────────────────────────────────────┤
│                                                   │
│ 🔄 クロール: 美容                    実行中 45秒  │
│    12/25件 処理中...                              │
│    ━━━━━━━━━━━━━━━━━━━━━━━━━━ 48%              │
│                                                   │
│ 🔄 メディア抽出: ad_abc123          実行中 120秒  │
│    Playwright起動中...                            │
│                                                   │
│ 🔄 スコア計算                        実行中 5秒   │
│    58件 計算中...                                 │
│                                                   │
│ ✅ クロール: サプリ                  完了 38秒     │
│    25件取得、新規12件                 2分前        │
│                                                   │
│ ❌ メディア抽出: ad_xyz789          失敗          │
│    TimeoutError: 30s exceeded        5分前        │
│    [再試行]                                       │
│                                                   │
└─────────────────────────────────────────────────┘
```

### プログレスバーの仕組み

```python
# Worker から進捗を更新
def update_progress(job_id, current, total, message=None):
    """ジョブの進捗を更新"""
    db.execute(
        text("""
            UPDATE jobs SET
                result = jsonb_set(
                    COALESCE(result, '{}'),
                    '{progress}',
                    :progress::jsonb
                ),
                updated_at = NOW()
            WHERE id = :job_id
        """),
        {
            "job_id": job_id,
            "progress": json.dumps({
                "current": current,
                "total": total,
                "percentage": round(current / total * 100),
                "message": message,
            })
        }
    )
    db.commit()

# クロールジョブ内で使用
for i, ad in enumerate(ads):
    process_ad(ad)
    update_progress(job_id, i + 1, len(ads), f"広告 {ad.title} を処理中")
```

---

## アラート設定

### ジョブ失敗アラート

```python
# 失敗率が閾値を超えたら通知

def check_job_health():
    last_hour = datetime.utcnow() - timedelta(hours=1)

    stats = db.execute(text("""
        SELECT type,
               COUNT(*) as total,
               SUM(CASE WHEN status = 'failed' THEN 1 ELSE 0 END) as failed
        FROM jobs
        WHERE created_at > :since
        GROUP BY type
    """), {"since": last_hour}).fetchall()

    for row in stats:
        failure_rate = row.failed / row.total if row.total > 0 else 0
        if failure_rate > 0.3:  # 30%以上失敗
            send_alert(
                f"ジョブ失敗率警告: {row.type} = {failure_rate:.0%}",
                f"過去1時間: {row.total}件中{row.failed}件失敗"
            )
```

### DLQ 監視

```bash
# SQS DLQ のメッセージ数を監視
aws sqs get-queue-attributes \
  --queue-url $DLQ_URL \
  --attribute-names ApproximateNumberOfMessages

# メッセージ数 > 0 ならアラート
```

---

## 実装優先度

```
[Phase 1: 可視化]
  1. jobs テーブル作成
  2. ジョブ作成時にDB記録
  3. Worker での状態更新
  4. GET /jobs API
  5. フロントに簡易ジョブリスト

[Phase 2: 管理]
  6. キャンセル / 再実行
  7. プログレスバー
  8. ジョブ統計API
  9. DLQ 確認UI

[Phase 3: 自動化]
  10. 失敗アラート
  11. 自動リトライロジック改善
  12. ジョブスケジューラー（定期クロール等）
  13. ジョブ依存関係（クロール完了 → スコア計算 → 通知）
```
