# APIレートリミット視点 — 過負荷からシステムを守る

## なぜ必要か

- Lambda は同時実行数制限（デフォルト1000）
- RDS は接続数制限（db.t3.micro で約60接続）
- Meta API は200 calls/hour
- 悪意あるリクエスト or バグで大量リクエストが来る可能性
- クロール系APIは重い → 1リクエストで数分のDB操作

---

## レートリミット設計

### エンドポイント別リミット

```
[高頻度OK: 読み取り系]
GET  /api/v1/rankings/pro-ranking     → 60 req/min/user
GET  /api/v1/ads/{id}                 → 120 req/min/user
GET  /api/v1/rankings/dashboard-*     → 30 req/min/user
GET  /api/v1/rankings/categories      → 30 req/min/user

[中頻度: 書き込み系]
POST /api/v1/rankings/quick-crawl     → 5 req/hour/user
POST /api/v1/collections              → 30 req/min/user
POST /api/v1/ads/export/*             → 10 req/hour/user

[低頻度: 重い処理]
POST /api/v1/rankings/recompute-scores → 2 req/hour/global
POST /api/v1/media/extract            → 10 req/hour/user
POST /api/v1/creative/generate        → 20 req/hour/user
POST /api/v1/lp/analyze               → 10 req/hour/user

[最低頻度: 管理系]
POST /api/v1/settings/*               → 10 req/min/user
POST /api/v1/webhooks                 → 5 req/min/user
```

---

## 実装方法

### 方法1: Lambda + API Gateway (設定のみ)

```
API Gateway のスロットリングで設定可能:
  ステージレベル: 1000 req/sec（バースト: 2000）
  メソッドレベル: 個別に設定

設定方法 (terraform):
  resource "aws_api_gateway_method_settings" "rankings" {
    rest_api_id = aws_api_gateway_rest_api.api.id
    stage_name  = "production"
    method_path = "rankings/GET"
    settings {
      throttling_rate_limit  = 100
      throttling_burst_limit = 200
    }
  }
```

### 方法2: FastAPI ミドルウェア (柔軟)

```python
# app/middleware/rate_limit.py
from collections import defaultdict
import time

class RateLimiter:
    def __init__(self):
        self.requests = defaultdict(list)

    def is_allowed(self, key: str, max_requests: int, window_seconds: int) -> bool:
        now = time.time()
        window_start = now - window_seconds

        # 古いリクエストを削除
        self.requests[key] = [
            t for t in self.requests[key] if t > window_start
        ]

        if len(self.requests[key]) >= max_requests:
            return False

        self.requests[key].append(now)
        return True

    def get_remaining(self, key: str, max_requests: int, window_seconds: int) -> int:
        now = time.time()
        window_start = now - window_seconds
        current = len([t for t in self.requests[key] if t > window_start])
        return max(0, max_requests - current)

rate_limiter = RateLimiter()

# ミドルウェア
@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    # IPベースのキー（認証後はuser_idベース）
    client_ip = request.client.host
    path = request.url.path
    method = request.method

    # エンドポイント別のリミット設定
    limits = get_rate_limit(method, path)
    if limits:
        key = f"{client_ip}:{method}:{path}"
        if not rate_limiter.is_allowed(key, limits["max"], limits["window"]):
            remaining = 0
            return JSONResponse(
                status_code=429,
                content={"error": "Rate limit exceeded", "retry_after": limits["window"]},
                headers={
                    "X-RateLimit-Limit": str(limits["max"]),
                    "X-RateLimit-Remaining": "0",
                    "X-RateLimit-Reset": str(int(time.time()) + limits["window"]),
                    "Retry-After": str(limits["window"]),
                }
            )

    response = await call_next(request)

    # レートリミットヘッダー追加
    if limits:
        remaining = rate_limiter.get_remaining(key, limits["max"], limits["window"])
        response.headers["X-RateLimit-Limit"] = str(limits["max"])
        response.headers["X-RateLimit-Remaining"] = str(remaining)

    return response
```

### Lambda のインメモリキャッシュの注意

```
Lambda はステートレス:
  - コールドスタート時にrate_limiterがリセットされる
  - 複数インスタンスが同時実行 → 各自のカウンター

対策:
  1. DynamoDB でカウンター管理（原子的操作）
  2. API Gateway のスロットリングに委ねる（推奨）
  3. CloudFront の WAF ルールで制御
```

---

## Meta API レートリミットの管理

### 現在の制約

```
Ad Library API:
  - 200 calls/hour（App Development レベル）
  - 各リクエスト最大25件
  - 1時間最大5000広告ID

Marketing API:
  - アクセスレベルに依存
  - 通常: 200 calls/hour
  - 上位: 60,000 calls/hour
```

### クロール頻度の最適化

```python
# app/services/crawling/rate_manager.py

class MetaApiRateManager:
    MAX_CALLS_PER_HOUR = 200
    SAFETY_MARGIN = 0.8  # 80%まで使用

    def __init__(self):
        self.calls_this_hour = 0
        self.hour_start = time.time()

    def can_make_call(self) -> bool:
        self._reset_if_new_hour()
        return self.calls_this_hour < self.MAX_CALLS_PER_HOUR * self.SAFETY_MARGIN

    def record_call(self):
        self._reset_if_new_hour()
        self.calls_this_hour += 1

    def remaining_calls(self) -> int:
        self._reset_if_new_hour()
        return int(self.MAX_CALLS_PER_HOUR * self.SAFETY_MARGIN) - self.calls_this_hour

    def wait_time_seconds(self) -> int:
        """次のリセットまでの待ち時間"""
        elapsed = time.time() - self.hour_start
        return max(0, 3600 - int(elapsed))

    def _reset_if_new_hour(self):
        if time.time() - self.hour_start >= 3600:
            self.calls_this_hour = 0
            self.hour_start = time.time()
```

### クロールのバジェット配分

```
1時間に160コール（200×80%）使える:
  - キーワードクロール: 各キーワード 3-5コール
  - → 30-50キーワード/時間

配分戦略:
  優先度1（毎日）: メインカテゴリ × 5キーワード = 25コール
  優先度2（週2回）: サブカテゴリ × 10キーワード = 50コール
  優先度3（週1回）: 新キーワード発掘 × 5 = 25コール
  バッファ: 60コール（手動クロール/再試行用）
```

---

## DDoS対策

### CloudFront + WAF

```
WAF ルール:
  1. レートベース: 5000 req/5min/IP → ブロック
  2. 地理制限: 日本のみ（必要に応じて）
  3. SQLインジェクション検出
  4. XSS検出
  5. 既知の悪意あるIPリスト

コスト: WAF $5/月 + $0.60/百万リクエスト
```

### CloudFront のレートリミット

```hcl
# terraform/waf.tf
resource "aws_wafv2_web_acl" "vaap" {
  name  = "vaap-rate-limit"
  scope = "CLOUDFRONT"

  default_action { allow {} }

  rule {
    name     = "rate-limit-per-ip"
    priority = 1

    action { block {} }

    statement {
      rate_based_statement {
        limit              = 5000
        aggregate_key_type = "IP"
      }
    }

    visibility_config {
      sampled_requests_enabled   = true
      cloudwatch_metrics_enabled = true
      metric_name                = "vaap-rate-limit"
    }
  }
}
```

---

## レスポンスヘッダー

```
成功時:
  HTTP/1.1 200 OK
  X-RateLimit-Limit: 60
  X-RateLimit-Remaining: 45
  X-RateLimit-Reset: 1709312400

制限超過時:
  HTTP/1.1 429 Too Many Requests
  X-RateLimit-Limit: 60
  X-RateLimit-Remaining: 0
  X-RateLimit-Reset: 1709312400
  Retry-After: 45
  Content-Type: application/json
  {"error": {"code": "RATE_LIMITED", "message": "Too many requests. Try again in 45 seconds."}}
```

---

## フロントエンドの対応

```typescript
// lib/api.ts の改善

async function apiCall(url: string, options?: RequestInit) {
  const response = await fetch(url, options);

  if (response.status === 429) {
    const retryAfter = parseInt(response.headers.get('Retry-After') || '60');
    // ユーザーに通知
    showToast({
      type: 'warning',
      message: `リクエスト制限に達しました。${retryAfter}秒後に再試行してください。`,
    });
    // 自動リトライ
    await new Promise(resolve => setTimeout(resolve, retryAfter * 1000));
    return apiCall(url, options);  // 1回だけリトライ
  }

  return response;
}
```

---

## 実装優先度

```
[Phase 1: 基本防御]
  1. API Gateway のスロットリング設定
  2. 429レスポンスの統一フォーマット
  3. フロントの429ハンドリング

[Phase 2: 細かい制御]
  4. エンドポイント別レートリミット
  5. Meta API コール管理
  6. レートリミットヘッダーの追加

[Phase 3: 高度な防御]
  7. WAF の導入
  8. DynamoDB ベースの分散レートリミット
  9. ユーザー/プラン別のリミット
```
