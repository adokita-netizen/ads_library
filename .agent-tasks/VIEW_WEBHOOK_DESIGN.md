# Webhook設計視点 — 外部システムとの連携インターフェース

## なぜWebhookが必要か

- クロール完了時にSlackに通知したい
- ヒット広告発見時に自動でレポート生成したい
- 外部BI（Googleスプレッドシート等）にデータ自動連携したい
- Zapier/Make 経由で非エンジニアもワークフロー構築可能にしたい

---

## Webhook イベント設計

### イベント一覧

```
crawl.completed       → クロール完了時
crawl.failed          → クロール失敗時
ad.new                → 新しい広告がDBに追加された時
ad.hit_detected       → ヒット広告が検出された時
ad.big_hit_detected   → 大ヒット広告が検出された時
ad.stopped            → 広告の配信停止を検知した時
score.recalculated    → スコア再計算完了時
media.extracted       → メディア抽出完了時
export.completed      → エクスポート完了時
token.expiring        → Meta APIトークン期限切れ7日前
token.expired         → Meta APIトークン期限切れ
```

### イベントペイロード

```json
// crawl.completed
{
  "event": "crawl.completed",
  "timestamp": "2025-03-01T12:00:00Z",
  "data": {
    "keyword": "美容",
    "total_found": 25,
    "new_ads": 12,
    "updated_ads": 8,
    "hit_ads": 3,
    "duration_seconds": 45
  }
}

// ad.hit_detected
{
  "event": "ad.hit_detected",
  "timestamp": "2025-03-01T12:01:00Z",
  "data": {
    "ad_id": "abc123",
    "ad_archive_id": "12345678",
    "title": "【衝撃】美容液が...",
    "hit_score": 85,
    "hit_level": "大HIT",
    "category": "美容",
    "platform": "facebook",
    "page_name": "XXX公式",
    "signals": {
      "longevity": 90,
      "spend": 80,
      "active_bonus": 10,
      "creative_quality": 75,
      "trend": 85
    }
  }
}
```

---

## Webhook 管理API

### エンドポイント

```
POST   /api/v1/webhooks                → Webhook登録
GET    /api/v1/webhooks                → 一覧取得
GET    /api/v1/webhooks/{id}           → 詳細取得
PATCH  /api/v1/webhooks/{id}           → 更新
DELETE /api/v1/webhooks/{id}           → 削除
POST   /api/v1/webhooks/{id}/test      → テスト送信
GET    /api/v1/webhooks/{id}/deliveries → 配信履歴
```

### 登録リクエスト

```json
POST /api/v1/webhooks
{
  "url": "https://hooks.slack.com/services/T.../B.../xxx",
  "events": ["crawl.completed", "ad.hit_detected"],
  "secret": "whsec_abc123...",
  "active": true,
  "metadata": {
    "name": "Slack通知",
    "description": "ヒット広告をSlackに通知"
  }
}
```

---

## Webhook 配信エンジン

### 配信フロー

```
イベント発生
  ↓
webhook_events テーブルに記録
  ↓
SQS にメッセージ送信（非同期配信）
  ↓
Worker が SQS からメッセージ取得
  ↓
登録された URL に POST リクエスト
  ↓
成功 → delivery_log に記録
失敗 → リトライキューに入れる（指数バックオフ）
```

### リトライ戦略

```
1回目: 即時
2回目: 1分後
3回目: 5分後
4回目: 30分後
5回目: 2時間後
6回目以降: 配信停止、webhook を disabled に

合計: 最大5回リトライ、約2.5時間
```

### 署名検証

```python
import hmac
import hashlib

def sign_payload(payload: str, secret: str) -> str:
    """HMAC-SHA256で署名"""
    return hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()

# 配信時のヘッダー
headers = {
    "Content-Type": "application/json",
    "X-VAAP-Webhook-ID": webhook_id,
    "X-VAAP-Webhook-Timestamp": timestamp,
    "X-VAAP-Webhook-Signature": f"sha256={signature}",
    "User-Agent": "VAAP-Webhook/1.0",
}
```

### 受信側の検証（ドキュメント用）

```python
# 受信者が署名を検証するサンプル
import hmac, hashlib

def verify_webhook(payload, signature, secret):
    expected = hmac.new(
        secret.encode(),
        payload.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(f"sha256={expected}", signature)
```

---

## DBスキーマ

```sql
CREATE TABLE webhooks (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID REFERENCES tenants(id),
    url VARCHAR(2048) NOT NULL,
    secret VARCHAR(256),
    events TEXT[] NOT NULL,  -- {"crawl.completed", "ad.hit_detected"}
    active BOOLEAN DEFAULT TRUE,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    last_triggered_at TIMESTAMP,
    failure_count INTEGER DEFAULT 0
);

CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    webhook_id UUID REFERENCES webhooks(id),
    event VARCHAR(50) NOT NULL,
    payload JSONB NOT NULL,
    response_status INTEGER,
    response_body TEXT,
    duration_ms INTEGER,
    success BOOLEAN,
    attempt INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_deliveries_webhook ON webhook_deliveries (webhook_id, created_at DESC);
```

---

## Slack連携の例

### Slack Incoming Webhook

```python
# Slack用のフォーマッター
def format_slack_message(event_type, data):
    if event_type == "ad.hit_detected":
        return {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🎯 ヒット広告を発見！"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*タイトル:*\n{data['title']}"},
                        {"type": "mrkdwn", "text": f"*スコア:*\n{data['hit_score']}"},
                        {"type": "mrkdwn", "text": f"*レベル:*\n{data['hit_level']}"},
                        {"type": "mrkdwn", "text": f"*ジャンル:*\n{data['category']}"},
                    ]
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "VEAPで見る"},
                            "url": f"https://vaap.jp/ad/{data['ad_id']}"
                        }
                    ]
                }
            ]
        }
```

---

## Google Sheets 連携の例

### Zapier/Make 経由

```
VAAP Webhook → Zapier → Google Sheets

設定:
1. Zapier で Webhook トリガーを作成
2. VAAP でその URL を Webhook として登録
3. Zapier で Google Sheets の行追加アクションを設定
4. フィールドマッピング:
   ad_id → A列
   title → B列
   hit_score → C列
   category → D列
   platform → E列
   detected_at → F列
```

---

## テスト配信

```bash
# Webhook のテスト配信
curl -X POST "http://localhost:8000/api/v1/webhooks/{id}/test" \
  -H "Authorization: Bearer TOKEN"

# レスポンス
{
  "status": "delivered",
  "response_status": 200,
  "duration_ms": 234,
  "payload": {
    "event": "test.ping",
    "timestamp": "2025-03-01T12:00:00Z",
    "data": {"message": "This is a test webhook delivery from VAAP"}
  }
}
```

---

## 実装優先度

```
[Phase 1] 基盤
  1. webhooks テーブル + CRUD API
  2. イベント発火ポイントの実装（crawl_complete, hit_detected）
  3. 同期配信（リトライなし）
  4. テスト配信機能

[Phase 2] 信頼性
  5. SQS 経由の非同期配信
  6. リトライロジック
  7. 配信履歴の記録と確認UI
  8. 署名検証

[Phase 3] 拡張
  9. Slack テンプレート
  10. フロントエンドのWebhook管理画面
  11. Zapier/Make 連携ドキュメント
  12. レート制限（1分に10回まで等）
```

---

## セキュリティ考慮

```
- URL はHTTPSのみ許可（ローカルIP除外）
- secret は暗号化して保存
- レスポンスボディは1KB以上保存しない
- 配信タイムアウト: 10秒
- 1つのWebhookが障害 → 他のWebhookに影響しない
- プライベートネットワークへのリクエスト禁止（SSRF対策）
```
