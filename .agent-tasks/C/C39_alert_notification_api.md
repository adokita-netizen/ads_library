# C39: アラート & 通知 API

## 概要
A37のアラートエンジンが生成したアラートをフロントエンドに配信するAPIを構築する。
B42の通知センターUIのバックエンド。

## 背景
A37でアラートルール + AlertHistory テーブルが作成される。
B42でフロントエンドの通知UIが構築される。
この C39 はその橋渡しとなるAPI層を担当する。

## タスク

### Task 1: 通知取得エンドポイント
```python
# backend/app/api/endpoints/notifications.py に追加

@router.get("/recent")
async def get_recent_notifications(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """最新N件の通知を取得（ベルアイコン用）"""
    # AlertHistory から user_id でフィルタ、created_at DESC で取得

@router.get("/")
async def list_notifications(
    page: int = 1,
    per_page: int = 20,
    filter: str = "all",  # all, unread, alert, system
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """通知一覧（ページネーション付き）"""

@router.get("/unread-count")
async def get_unread_count(
    db: AsyncSession = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """未読通知数（ポーリング用、軽量レスポンス）"""
    return {"count": unread_count}

@router.put("/{notification_id}/read")
async def mark_as_read(notification_id: int, ...):
    """通知を既読にする"""

@router.put("/read-all")
async def mark_all_as_read(...):
    """全通知を既読にする"""
```

### Task 2: アラートルール管理エンドポイント
```python
@router.get("/rules")
async def list_alert_rules(...):
    """ユーザーのアラートルール一覧"""

@router.post("/rules")
async def create_alert_rule(rule: AlertRuleCreate, ...):
    """新しいアラートルールを作成"""
    # rule_type: new_hit, trend_spike, competitor_new, score_change
    # conditions: {"genre": "美容", "min_score": 70}

@router.put("/rules/{rule_id}")
async def update_alert_rule(rule_id: int, rule: AlertRuleUpdate, ...):
    """アラートルールを更新"""

@router.delete("/rules/{rule_id}")
async def delete_alert_rule(rule_id: int, ...):
    """アラートルールを削除"""

@router.put("/rules/{rule_id}/toggle")
async def toggle_alert_rule(rule_id: int, ...):
    """アラートルールの有効/無効を切り替え"""
```

### Task 3: システム通知生成サービス
```python
# backend/app/services/notification_service.py (新規)

class NotificationService:
    """システムイベントから通知を生成する"""

    @staticmethod
    async def notify_crawl_completed(user_id: int, job_id: str, ads_count: int):
        """クロール完了通知"""
        await AlertHistory.create(
            user_id=user_id,
            alert_type="system",
            title=f"クロール完了: {ads_count}件の広告を取得",
            data={"job_id": job_id, "ads_count": ads_count}
        )

    @staticmethod
    async def notify_ranking_updated(user_id: int):
        """ランキング更新通知"""

    @staticmethod
    async def notify_export_ready(user_id: int, export_url: str):
        """エクスポート完了通知"""

    @staticmethod
    async def notify_media_extracted(user_id: int, ad_id: int):
        """メディア抽出完了通知"""
```

### Task 4: Pydantic スキーマ定義
```python
# backend/app/schemas/notification.py (新規)

class NotificationResponse(BaseModel):
    id: int
    alert_type: str           # "new_hit", "trend_spike", "system"
    title: str
    body: Optional[str]
    data: Optional[dict]
    is_read: bool
    created_at: datetime

class AlertRuleCreate(BaseModel):
    name: str
    rule_type: str            # new_hit, trend_spike, competitor_new, score_change
    conditions: dict
    notification_channels: list[str] = ["in_app"]
    cooldown_minutes: int = 60

class AlertRuleResponse(BaseModel):
    id: int
    name: str
    rule_type: str
    conditions: dict
    is_active: bool
    trigger_count: int
    last_triggered_at: Optional[datetime]

class UnreadCountResponse(BaseModel):
    count: int
```

## API一覧
| Method | Path | 説明 |
|--------|------|------|
| GET | /notifications/recent | 最新N件の通知 |
| GET | /notifications/ | 通知一覧（ページネーション） |
| GET | /notifications/unread-count | 未読数 |
| PUT | /notifications/{id}/read | 既読にする |
| PUT | /notifications/read-all | 全既読 |
| GET | /notifications/rules | ルール一覧 |
| POST | /notifications/rules | ルール作成 |
| PUT | /notifications/rules/{id} | ルール更新 |
| DELETE | /notifications/rules/{id} | ルール削除 |
| PUT | /notifications/rules/{id}/toggle | ルール有効/無効切替 |

## 完了条件
- [x] 通知CRUD APIが動作する
- [x] アラートルールCRUD APIが動作する
- [x] unread-count が軽量レスポンスで返る
- [x] NotificationService が各種イベント通知を生成できる
- [x] Pydantic スキーマでバリデーションされている

## 触っていいファイル
- backend/app/api/endpoints/notifications.py (既存拡張)
- backend/app/services/notification_service.py (新規)
- backend/app/schemas/notification.py (新規)

## 依存
- A37 (alert_rules / alert_history テーブル) の完成が必要
- テーブルが未完成の場合はモックデータで実装可能

