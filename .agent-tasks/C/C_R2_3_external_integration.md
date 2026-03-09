# C-R2-3: External Integration API (C40 Phase 2)
# 優先度: P1 | 前提: C-R2-2 | ブロック: なし

## 目的
Slack通知、Webhook配信、CSV定期配信のAPI を提供する。

## 対象ファイル (全て Agent C 専有)
- 新規: `backend/app/api/endpoints/integrations.py`
- 新規: `backend/app/services/integrations/slack_notifier.py`
- 新規: `backend/app/services/integrations/webhook_sender.py`
- 新規: `backend/app/services/integrations/csv_exporter.py`

## APIエンドポイント

### Slack連携

#### POST /api/v1/integrations/slack/configure
```python
@router.post("/slack/configure")
async def configure_slack(
    request: SlackConfigRequest,  # { webhook_url: str, channel: str|null }
    db: Session = Depends(get_db)
):
    """Slack Webhook URL を設定"""
    # settings テーブル or 環境変数に保存
```

#### POST /api/v1/integrations/slack/test
```python
@router.post("/slack/test")
async def test_slack(db: Session = Depends(get_db)):
    """テスト通知を送信"""
    # Slack Webhook に POST
    import httpx
    payload = {
        "text": "VAAP Test Notification",
        "blocks": [
            {"type": "header", "text": {"type": "plain_text", "text": "VAAP - Test Notification"}},
            {"type": "section", "text": {"type": "mrkdwn", "text": "Slack integration is working!"}}
        ]
    }
    async with httpx.AsyncClient() as client:
        resp = await client.post(webhook_url, json=payload, timeout=10)
    return {"success": resp.status_code == 200}
```

### Webhook配信

#### POST /api/v1/integrations/webhooks
```python
@router.post("/webhooks")
async def create_webhook(
    request: WebhookCreateRequest,
    db: Session = Depends(get_db)
):
    """
    Request:
    {
        "url": "https://example.com/webhook",
        "events": ["new_hit_ad", "score_change", "crawl_complete"],
        "secret": "optional-hmac-secret",
        "is_active": true
    }
    """
```

#### GET /api/v1/integrations/webhooks
```python
@router.get("/webhooks")
async def list_webhooks(db: Session = Depends(get_db)):
    """Webhook一覧"""
```

#### DELETE /api/v1/integrations/webhooks/{id}
```python
@router.delete("/webhooks/{webhook_id}")
async def delete_webhook(webhook_id: int, db: Session = Depends(get_db)):
    """Webhook削除"""
```

### CSV定期配信

#### POST /api/v1/integrations/scheduled-export
```python
@router.post("/scheduled-export")
async def create_scheduled_export(
    request: ScheduledExportRequest,
    db: Session = Depends(get_db)
):
    """
    Request:
    {
        "name": "Weekly HIT Report",
        "schedule": "weekly",  // daily, weekly, monthly
        "format": "csv",       // csv, json
        "filters": { "genre": "beauty", "min_score": 45 },
        "delivery": {
            "type": "slack",   // slack, webhook, email
            "target": "https://hooks.slack.com/..."
        }
    }
    """
```

### WebhookSender サービス
```python
# backend/app/services/integrations/webhook_sender.py
import hashlib
import hmac
import httpx

class WebhookSender:
    async def send(self, webhook_url: str, event: str, payload: dict, secret: str = None):
        headers = {"Content-Type": "application/json", "X-VAAP-Event": event}

        if secret:
            body = json.dumps(payload).encode()
            signature = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
            headers["X-VAAP-Signature"] = f"sha256={signature}"

        async with httpx.AsyncClient() as client:
            try:
                resp = await client.post(webhook_url, json=payload, headers=headers, timeout=10)
                return {"success": resp.status_code < 400, "status": resp.status_code}
            except Exception as e:
                return {"success": False, "error": str(e)}
```

## ルーター登録
```python
# backend/app/main.py に追加
from app.api.endpoints import integrations
app.include_router(integrations.router, prefix="/api/v1/integrations", tags=["Integrations"])
```

## 完了条件
- [x] Slack 設定 + テスト送信が動作する
- [x] Webhook CRUD が動作する
- [x] Webhook 配信に HMAC 署名が付く
- [x] 定期エクスポート設定が保存される
- [x] status.md に記録

