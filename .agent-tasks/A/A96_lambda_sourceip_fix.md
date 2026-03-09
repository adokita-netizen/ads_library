# A96: Lambda API Gateway sourceIp エラー修正

## 優先度: 🅰️ A（クリティカル・本番ブロッカー）

## 問題
- API Gateway経由のリクエストで `sourceIp` KeyErrorが発生
- health-response.json にエラー記録あり
- Mangumアダプタが期待するHTTPリクエストコンテキスト形式とAPI Gatewayの実際の形式が不一致
- 影響: API Gateway経由で全APIエンドポイントが到達不可の可能性

## 原因調査
1. `lambda_handler.py` のリクエストコンテキスト解析部分を確認
2. API Gateway REST API vs HTTP API のイベント形式の違いを確認
3. Mangumの `api_gateway_base_path` 設定を確認

## 対象ファイル
- `backend/lambda_handler.py`
- `terraform/api_gateway.tf`（設定確認）

## 修正方針

### 1. requestContext の安全なアクセス
```python
# Before: sourceIp直アクセスでKeyError
source_ip = event["requestContext"]["identity"]["sourceIp"]

# After: 安全なフォールバック
request_context = event.get("requestContext", {})
identity = request_context.get("identity", {})
source_ip = identity.get("sourceIp", "unknown")
```

### 2. Mangumイベント形式の検証
- REST API (v1) と HTTP API (v2) でイベント構造が異なる
- 現在のAPI Gatewayタイプに合わせてMangumの設定を確認
```python
from mangum import Mangum
handler = Mangum(app, lifespan="off", api_gateway_base_path="/api")
```

### 3. ヘルスチェックの修正
- `/health` エンドポイントがAPI Gateway経由で正常応答することを確認
- エラー時にもJSON形式で応答を返す

## 完了条件
- [x] API Gateway経由のヘルスチェックが200を返す（ローカル最小再現イベントでMangum前処理を検証）
- [x] sourceIp KeyErrorが発生しない（`requestContext.http.sourceIp` / `requestContext.identity.sourceIp` を安全補完）
- [x] 既存のLambda直接呼び出し（cleanup等）に影響しない（action分岐構造は未変更）
- [ ] CloudWatch Logsでエラーなし確認（本番デプロイ後の運用確認待ち）

## Status
Completed (2026-03-05, code fix + local validation)

## 制約
- `lambda_handler.py` のみ修正（Agent A専有領域）
- 既存アクション分岐構造は変更しない
