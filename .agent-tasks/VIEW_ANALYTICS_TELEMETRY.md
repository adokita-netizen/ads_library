# 分析・テレメトリ視点 — プロダクトの使われ方を可視化する

## なぜテレメトリが必要か

- どの機能が使われているか分からない → 無駄な機能開発のリスク
- ユーザーがどこで離脱するか分からない → UX改善の根拠がない
- パフォーマンスのボトルネックが見えない → 盲目的な最適化
- エラーの発生頻度が分からない → 障害対応が後手

---

## テレメトリ設計

### 3層テレメトリ

```
Layer 1: インフラメトリクス (AWS CloudWatch)
  → CPU, Memory, Latency, Error Rate, Queue Depth

Layer 2: アプリケーションログ (構造化ログ)
  → リクエスト/レスポンス、処理時間、エラー詳細

Layer 3: ユーザー行動 (フロントエンド)
  → ページビュー、クリック、フィルター使用、滞在時間
```

---

## Layer 1: インフラメトリクス

### 既存の CloudWatch メトリクス

```
Lambda (vaap-production-api):
  - Invocations          → リクエスト数
  - Duration             → 処理時間
  - Errors               → エラー数
  - Throttles            → スロットリング
  - ConcurrentExecutions → 同時実行数
  - ColdStarts (custom)  → コールドスタート頻度

ECS (vaap-production-worker):
  - CPUUtilization       → CPU使用率
  - MemoryUtilization    → メモリ使用率
  - RunningTaskCount     → 稼働タスク数

SQS:
  - ApproximateNumberOfMessagesVisible → 待ちメッセージ数
  - ApproximateAgeOfOldestMessage      → 最古メッセージ待機時間
  - NumberOfMessagesSent               → 送信数
  - NumberOfMessagesReceived           → 受信数

RDS:
  - DatabaseConnections  → DB接続数
  - ReadLatency          → 読み取りレイテンシ
  - WriteLatency         → 書き込みレイテンシ
  - FreeStorageSpace     → 残りストレージ
```

### カスタムメトリクス（追加推奨）

```python
import boto3

cloudwatch = boto3.client('cloudwatch')

def put_metric(name, value, unit='Count'):
    cloudwatch.put_metric_data(
        Namespace='VAAP/Application',
        MetricData=[{
            'MetricName': name,
            'Value': value,
            'Unit': unit,
        }]
    )

# 使用例
put_metric('CrawledAdsCount', 25)
put_metric('HitAdsFound', 3)
put_metric('MediaExtractionSuccess', 20)
put_metric('MediaExtractionFailed', 5)
put_metric('ScoreRecalculationDuration', 45.2, 'Seconds')
```

---

## Layer 2: アプリケーションログ

### 構造化ログの設計

```python
import json
import logging
import time
from uuid import uuid4

class StructuredLogger:
    def __init__(self, service_name: str):
        self.service = service_name
        self.logger = logging.getLogger(service_name)

    def log(self, event: str, **kwargs):
        entry = {
            "timestamp": time.time(),
            "service": self.service,
            "event": event,
            **kwargs
        }
        self.logger.info(json.dumps(entry, ensure_ascii=False))

logger = StructuredLogger("vaap-api")

# リクエストログ
logger.log("api_request",
    method="GET",
    path="/api/v1/rankings/pro-ranking",
    query_params={"page": 1, "sort": "hit_score"},
    duration_ms=234,
    status=200,
    response_size=15420
)

# クロールログ
logger.log("crawl_complete",
    keyword="美容",
    ads_found=25,
    new_ads=12,
    duration_seconds=45,
    api_calls_used=3
)

# エラーログ
logger.log("error",
    error_type="DatabaseError",
    message="Connection refused",
    endpoint="/api/v1/rankings/pro-ranking",
    traceback="..."
)
```

### FastAPI ミドルウェアでの自動ログ

```python
# app/middleware/logging.py
@app.middleware("http")
async def log_requests(request, call_next):
    request_id = str(uuid4())
    start = time.time()

    response = await call_next(request)

    duration = (time.time() - start) * 1000
    logger.log("api_request",
        request_id=request_id,
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=round(duration, 2),
        user_agent=request.headers.get("user-agent"),
    )

    return response
```

---

## Layer 3: ユーザー行動トラッキング

### フロントエンド イベント設計

```typescript
// lib/analytics.ts

interface AnalyticsEvent {
  event: string;
  properties?: Record<string, any>;
  timestamp: number;
}

class Analytics {
  private queue: AnalyticsEvent[] = [];

  track(event: string, properties?: Record<string, any>) {
    this.queue.push({
      event,
      properties,
      timestamp: Date.now(),
    });

    // バッチ送信（10件 or 30秒ごと）
    if (this.queue.length >= 10) {
      this.flush();
    }
  }

  async flush() {
    if (this.queue.length === 0) return;
    const events = [...this.queue];
    this.queue = [];

    await fetch('/api/v1/analytics/events', {
      method: 'POST',
      body: JSON.stringify({ events }),
    });
  }
}

export const analytics = new Analytics();
```

### トラッキングすべきイベント

```
ページ表示:
  page_view              → { view: "pro_ranking" }
  page_view              → { view: "hit_analysis" }

ランキング操作:
  filter_applied         → { type: "genre", value: "美容" }
  filter_applied         → { type: "platform", value: "facebook" }
  sort_changed           → { column: "hit_score", direction: "desc" }
  search_performed       → { query: "サプリ", results_count: 15 }
  page_changed           → { page: 2, total_pages: 10 }

広告詳細:
  ad_detail_opened       → { ad_id: "123", source: "table_row" }
  ad_detail_closed       → { ad_id: "123", duration_ms: 5000 }
  media_played           → { ad_id: "123", media_type: "video" }
  lp_link_clicked        → { ad_id: "123", url: "..." }

エクスポート:
  export_initiated       → { format: "csv", count: 100 }
  export_completed       → { format: "csv", duration_ms: 2000 }

エラー体験:
  error_displayed        → { type: "api_error", endpoint: "..." }
  empty_state_shown      → { view: "pro_ranking", reason: "no_data" }
```

---

## ダッシュボード設計

### プロダクトKPI

```
日次:
  DAU (Daily Active Users)           → 目標: -
  ページビュー数                      → 各ビューの人気度
  検索回数                            → 検索機能の利用度
  広告詳細の表示回数                  → コンテンツの消費度
  エクスポート回数                    → ビジネス利用度

週次:
  WAU (Weekly Active Users)          → 定着率
  フィルター使用率                    → フィルター機能の価値
  平均セッション時間                  → エンゲージメント
  機能別ファネル                      → 離脱ポイント

月次:
  MAU (Monthly Active Users)
  新機能の採用率
  NPS (Net Promoter Score) → 将来的にアンケート実装
```

### 技術KPI

```
API レイテンシ:
  p50: < 200ms
  p95: < 1000ms
  p99: < 3000ms

エラー率:
  5xx: < 0.1%
  4xx: < 5%

可用性:
  API uptime: > 99.5%
  Worker uptime: > 99%

データ鮮度:
  最新クロールからの経過時間: < 24時間
  スコア再計算からの経過時間: < 6時間
```

---

## 実装ロードマップ

### Phase 1: ログの構造化（即日）
```
1. FastAPI リクエストログの構造化
2. Worker タスクログの構造化
3. CloudWatch Logs Insights でクエリ可能に
```

### Phase 2: カスタムメトリクス（1週間）
```
1. CloudWatch カスタムメトリクスの送信
2. CloudWatch ダッシュボード作成
3. アラーム設定（エラー率、レイテンシ）
```

### Phase 3: ユーザー行動（2週間）
```
1. フロントエンドのイベントトラッキング実装
2. バックエンドのイベント受信API
3. 集計と可視化
```

### Phase 4: 分析基盤（1ヶ月）
```
1. イベントデータのS3エクスポート
2. Athena でのアドホッククエリ
3. QuickSight ダッシュボード
```

---

## プライバシー考慮

```
収集しないデータ:
  - 個人識別情報（PII）
  - IPアドレス（ハッシュ化 or 収集しない）
  - 広告の詳細テキスト（トラッキングには不要）

収集するデータ:
  - 匿名化されたユーザーID（セッション単位）
  - 操作イベント（何をクリックしたか）
  - タイミング（いつ、どのくらいの時間）
  - 技術情報（ブラウザ、画面サイズ）
```

---

## CloudWatch Logs Insights クエリ例

```sql
-- 遅いAPIリクエスト TOP10
fields @timestamp, path, duration_ms, status
| filter event = "api_request"
| filter duration_ms > 1000
| sort duration_ms desc
| limit 10

-- エラー率（時間帯別）
fields @timestamp
| filter event = "api_request"
| stats count(*) as total,
        sum(status >= 500) as errors
  by bin(1h)

-- 人気エンドポイント
fields path
| filter event = "api_request"
| stats count(*) as calls by path
| sort calls desc
| limit 20

-- クロール統計
fields @timestamp, keyword, ads_found, new_ads
| filter event = "crawl_complete"
| sort @timestamp desc
| limit 50
```
