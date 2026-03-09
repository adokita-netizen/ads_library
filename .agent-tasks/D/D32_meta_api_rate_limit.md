# D32: Meta API レートリミット・エラーハンドリング強化

## 問題
- `meta_crawler.py` で HTTP 429 (Rate Limit) をリトライ対象として処理していない
- 401 (Unauthorized) 時にトークン失効を検知してアラート通知しない
- レートリミット時の固定 sleep → exponential backoff にすべき

## 対象ファイル
- `backend/app/services/crawling/meta_crawler.py`

## 修正

### 1. HTTP ステータスコード別処理
```python
async def _request_with_retry(self, url: str, params: dict, max_retries: int = 3):
    for attempt in range(max_retries):
        response = await self.client.get(url, params=params)

        if response.status_code == 200:
            return response.json()

        if response.status_code == 429:
            # Rate limit: Retry-After ヘッダまたは exponential backoff
            retry_after = int(response.headers.get("Retry-After", 2 ** attempt * 5))
            logger.warning(f"Rate limited. Retry after {retry_after}s (attempt {attempt+1})")
            await asyncio.sleep(retry_after)
            continue

        if response.status_code == 401:
            # トークン失効 → リトライ不要、即座にアラート
            logger.error("Meta API token expired or invalid")
            _notify_token_expiry()
            raise MetaApiAuthError("Token expired")

        if response.status_code >= 500:
            # サーバーエラー → リトライ
            await asyncio.sleep(2 ** attempt)
            continue

        # その他のクライアントエラー → リトライしない
        raise MetaApiError(f"API error {response.status_code}: {response.text}")

    raise MetaApiError(f"Max retries ({max_retries}) exceeded")
```

### 2. トークン失効通知
```python
def _notify_token_expiry():
    """トークン失効をログ + CloudWatch メトリクスに記録"""
    logger.critical("META_API_TOKEN_EXPIRED — Manual renewal required")
    # CloudWatch カスタムメトリクス（オプション）
    try:
        import boto3
        cw = boto3.client("cloudwatch")
        cw.put_metric_data(
            Namespace="VAAP",
            MetricData=[{
                "MetricName": "MetaTokenExpired",
                "Value": 1,
                "Unit": "Count"
            }]
        )
    except Exception:
        pass  # メトリクス送信失敗は無視
```

### 3. リクエスト間隔の動的調整
```python
class RateLimiter:
    """429レスポンス頻度に応じてリクエスト間隔を動的調整"""
    def __init__(self, initial_interval: float = 1.0):
        self.interval = initial_interval
        self._consecutive_429 = 0

    def on_success(self):
        self._consecutive_429 = 0
        self.interval = max(0.5, self.interval * 0.9)  # 徐々に短縮

    def on_rate_limit(self):
        self._consecutive_429 += 1
        self.interval = min(60, self.interval * 2)  # 倍増（上限60s）
```

## 制約
- `meta_crawler.py` のみ修正
- クロール結果のデータ構造は変更しない
