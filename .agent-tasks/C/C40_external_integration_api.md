# C40: 外部サービス連携 API (Slack / Webhook / CSV自動配信)

## 概要
VAAPの分析結果を外部サービスに自動配信する機能のAPIを構築する。
Slack通知、Webhook、CSV定期配信に対応。

## 背景
広告代理店のワークフローでは、VAAPの画面だけでなく、
Slackで共有・スプレッドシートに転記・社内ツールに連携したいニーズがある。
外部連携はSaaSプロダクトの「粘着度」を高める重要な機能。

## タスク

### Task 1: Slack通知連携
```python
# backend/app/services/integrations/slack_notifier.py (新規)

class SlackNotifier:
    """Slack Incoming Webhookで通知を送信する"""

    async def send_new_hit_alert(self, webhook_url: str, ad: Ad):
        """新HIT広告の通知をSlackに送信"""
        payload = {
            "blocks": [
                {
                    "type": "header",
                    "text": {"type": "plain_text", "text": "🎯 新しいHIT広告を検出"}
                },
                {
                    "type": "section",
                    "fields": [
                        {"type": "mrkdwn", "text": f"*商材:* {ad.title}"},
                        {"type": "mrkdwn", "text": f"*スコア:* {ad.hit_score}"},
                        {"type": "mrkdwn", "text": f"*ジャンル:* {ad.genre}"},
                        {"type": "mrkdwn", "text": f"*広告主:* {ad.advertiser_name}"},
                    ]
                },
                {
                    "type": "actions",
                    "elements": [
                        {
                            "type": "button",
                            "text": {"type": "plain_text", "text": "VAAPで見る"},
                            "url": f"{settings.FRONTEND_URL}?view=ad-detail&id={ad.id}"
                        }
                    ]
                }
            ]
        }
        async with httpx.AsyncClient() as client:
            await client.post(webhook_url, json=payload)

    async def send_daily_summary(self, webhook_url: str, summary: dict):
        """日次サマリーをSlackに送信"""
```

### Task 2: 汎用Webhook配信
```python
# backend/app/services/integrations/webhook_dispatcher.py (新規)

class WebhookDispatcher:
    """登録されたWebhookエンドポイントにイベントを配信する"""

    async def dispatch(self, event_type: str, payload: dict):
        """
        event_type: "new_hit", "crawl_completed", "ranking_updated"
        payload: イベント固有のデータ
        """
        # 1. DBからアクティブなWebhook登録を取得
        # 2. 各Webhookにペイロード送信
        # 3. レスポンスコードを記録
        # 4. 失敗時はリトライキューに入れる

# backend/app/models/webhook.py (新規)
class WebhookEndpoint(Base):
    __tablename__ = "webhook_endpoints"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    url = Column(String(500), nullable=False)
    secret = Column(String(200))             # HMAC署名用シークレット
    events = Column(JSON, default=[])        # ["new_hit", "crawl_completed"]
    is_active = Column(Boolean, default=True)
    last_success_at = Column(DateTime, nullable=True)
    failure_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
```

### Task 3: CSV定期配信
```python
# backend/app/services/integrations/csv_scheduler.py (新規)

class CSVScheduler:
    """スケジュールに基づきCSVレポートを生成・配信する"""

    async def generate_and_deliver(self, schedule: ExportSchedule):
        """
        1. スケジュールの条件に基づき広告データを取得
        2. CSV生成
        3. S3にアップロード
        4. 配信先（メール/Slack/Webhook）に通知
        """

# backend/app/models/export_schedule.py (新規)
class ExportSchedule(Base):
    __tablename__ = "export_schedules"
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"))
    name = Column(String(200))               # "週次美容HIT広告レポート"
    frequency = Column(String(20))           # daily, weekly, monthly
    filters = Column(JSON)                   # {"genre": "美容", "min_score": 60}
    columns = Column(JSON)                   # ["title", "score", "spend"]
    delivery_method = Column(String(50))     # email, slack, webhook, s3
    delivery_config = Column(JSON)           # {"webhook_url": "...", "channel": "#reports"}
    next_run_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
```

### Task 4: APIエンドポイント
```python
# backend/app/api/endpoints/integrations.py (新規)

# --- Slack ---
@router.post("/slack/test")
async def test_slack_webhook(url: str):
    """Slack Webhook URLのテスト送信"""

@router.post("/slack/configure")
async def configure_slack(config: SlackConfig):
    """Slack Webhook URLの設定"""

# --- Webhook ---
@router.get("/webhooks")
@router.post("/webhooks")
@router.put("/webhooks/{id}")
@router.delete("/webhooks/{id}")
@router.post("/webhooks/{id}/test")
async def webhook_crud_and_test(...):
    """Webhook CRUD + テスト"""

# --- CSV Export Schedule ---
@router.get("/export-schedules")
@router.post("/export-schedules")
@router.put("/export-schedules/{id}")
@router.delete("/export-schedules/{id}")
@router.post("/export-schedules/{id}/run-now")
async def export_schedule_crud(...):
    """CSV配信スケジュール CRUD + 即時実行"""
```

## API一覧
| Method | Path | 説明 |
|--------|------|------|
| POST | /integrations/slack/test | Slack接続テスト |
| POST | /integrations/slack/configure | Slack設定保存 |
| GET/POST | /integrations/webhooks | Webhook一覧/作成 |
| PUT/DELETE | /integrations/webhooks/{id} | Webhook更新/削除 |
| POST | /integrations/webhooks/{id}/test | Webhookテスト送信 |
| GET/POST | /integrations/export-schedules | CSV配信一覧/作成 |
| PUT/DELETE | /integrations/export-schedules/{id} | CSV配信更新/削除 |
| POST | /integrations/export-schedules/{id}/run-now | CSV即時生成 |

## 完了条件
- [x] Slack通知が送信できる
- [x] Webhook登録・配信が動作する
- [x] CSV定期配信スケジュールが作成できる
- [x] Webhook にHMAC署名が付与される
- [x] 失敗時のリトライが動作する

## 触っていいファイル
- backend/app/api/endpoints/integrations.py (新規)
- backend/app/services/integrations/ (新規ディレクトリ)
- backend/app/models/webhook.py (新規)
- backend/app/models/export_schedule.py (新規)
- backend/app/schemas/integration.py (新規)
- migrations/ (Alembic)

