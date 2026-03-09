# C-R2-2: Alert Notification API (C39 Phase 2)
# 優先度: P0 | 前提: A-R2-6 (AlertEngine) が先なら連携、なくても独立実装可 | ブロック: B42 (Notification Center)

## 目的
通知CRUD + アラートルール管理の API を提供する。

## 対象ファイル (全て Agent C 専有)
- 新規 or 追加: `backend/app/api/endpoints/rankings.py` に追加 (14,779行に追記)
  または 新規: `backend/app/api/endpoints/notifications.py`
- 新規: `backend/app/services/notification_service.py`
- Agent A が作成予定: `backend/app/models/alert_rule.py`, `backend/app/models/alert_history.py`
  - Agent A 未完了の場合は Agent C がモデルを作成してよい（ただし COORDINATION_LOG で通知）

## APIエンドポイント

### 通知 CRUD

#### GET /api/v1/rankings/notifications
```python
@router.get("/notifications")
async def list_notifications(
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    unread_only: bool = Query(False),
    type_filter: str = Query(None),  # alert, new_ad, analysis_complete, system
    db: Session = Depends(get_db)
):
    """
    Response:
    {
        "notifications": [
            {
                "id": 1,
                "type": "new_ad",
                "title": "New HIT ad detected",
                "body": "Beauty genre: 'シミケア美容液' scored 85.2",
                "read": false,
                "created_at": "2026-03-01T10:00:00Z",
                "ad_id": 42,
                "action_url": null,
                "severity": "info",
                "metadata": {}
            }
        ],
        "unread_count": 5,
        "total": 42,
        "page": 1,
        "per_page": 20
    }
    """
```

#### PUT /api/v1/rankings/notifications/{id}/read
```python
@router.put("/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: int, db: Session = Depends(get_db)):
    """既読マーク"""
    # AlertHistory.is_read = True, read_at = datetime.utcnow()
```

#### PUT /api/v1/rankings/notifications/read-all
```python
@router.put("/notifications/read-all")
async def mark_all_notifications_read(db: Session = Depends(get_db)):
    """全既読"""
```

#### DELETE /api/v1/rankings/notifications/{id}
```python
@router.delete("/notifications/{notification_id}")
async def delete_notification(notification_id: int, db: Session = Depends(get_db)):
    """通知削除"""
```

### アラートルール管理

#### POST /api/v1/rankings/alert-rules
```python
@router.post("/alert-rules")
async def create_alert_rule(rule: AlertRuleCreate, db: Session = Depends(get_db)):
    """
    Request:
    {
        "name": "HIT Score Alert",
        "condition_type": "score_threshold",
        "target_field": "hit_score",
        "operator": "gt",
        "threshold": 80,
        "genre_filter": null,
        "notification_channel": "in_app",
        "cooldown_minutes": 60
    }
    """
```

#### GET /api/v1/rankings/alert-rules
```python
@router.get("/alert-rules")
async def list_alert_rules(db: Session = Depends(get_db)):
    """ルール一覧"""
```

#### PUT /api/v1/rankings/alert-rules/{id}
```python
@router.put("/alert-rules/{rule_id}")
async def update_alert_rule(rule_id: int, rule: AlertRuleUpdate, db: Session = Depends(get_db)):
    """ルール更新（有効/無効切替含む）"""
```

#### DELETE /api/v1/rankings/alert-rules/{id}
```python
@router.delete("/alert-rules/{rule_id}")
async def delete_alert_rule(rule_id: int, db: Session = Depends(get_db)):
    """ルール削除"""
```

### システム通知生成

#### NotificationService
```python
# backend/app/services/notification_service.py

class NotificationService:
    def __init__(self, session):
        self.session = session

    def create_notification(self, type: str, title: str, body: str,
                          ad_id: int = None, severity: str = "info", metadata: dict = None):
        """通知レコードを作成"""
        alert = AlertHistory(
            rule_id=None,  # 手動生成の場合
            ad_id=ad_id,
            alert_type=type,
            severity=severity,
            title=title,
            message=body,
            metadata=metadata or {},
        )
        self.session.add(alert)
        self.session.commit()
        return alert

    def notify_crawl_complete(self, new_count: int, total: int):
        self.create_notification(
            type="system",
            title="Crawl completed",
            body=f"{new_count} new ads collected. Total: {total}",
        )

    def notify_new_hit(self, ad_id: int, ad_title: str, score: float):
        self.create_notification(
            type="new_ad",
            title="New HIT ad detected",
            body=f"'{ad_title}' scored {score:.1f}",
            ad_id=ad_id,
            severity="info",
        )

    def notify_score_change(self, ad_id: int, ad_title: str, old_score: float, new_score: float):
        delta = new_score - old_score
        self.create_notification(
            type="alert",
            title="Score significant change",
            body=f"'{ad_title}' score changed by {delta:+.1f} ({old_score:.1f} → {new_score:.1f})",
            ad_id=ad_id,
            severity="warning" if abs(delta) > 20 else "info",
        )
```

### 既存コードへの統合ポイント
```python
# recompute_hit_scores.py の最後に通知呼び出しを追加
# → rankings.py の /compute-rankings エンドポイントの最後に:
notification_service = NotificationService(db)
for ad_id, new_score in newly_hit_ads:
    notification_service.notify_new_hit(ad_id, ...)

# quick-crawl の完了後に:
notification_service.notify_crawl_complete(new_count, total)
```

## COORDINATION_LOG に記載
```
[Planner 2 → Planner 3] Notification API 実装完了。
- GET /api/v1/rankings/notifications
- PUT /api/v1/rankings/notifications/{id}/read
- PUT /api/v1/rankings/notifications/read-all
- DELETE /api/v1/rankings/notifications/{id}
- GET/POST/PUT/DELETE /api/v1/rankings/alert-rules
レスポンス形式: { notifications: [...], unread_count, total }
Agent B は B42 で通知センターUIを作成してください。

[Planner 2 → Planner 1] AlertHistory テーブルを通知用に利用。
Agent A の AlertEngine が書き込んだレコードも表示対象。
モデル未作成の場合は Agent C が独自作成。
```

## 完了条件
- [x] 8つのエンドポイントが実装済み
- [x] NotificationService が通知生成できる
- [x] 既読/全既読/削除が動作する
- [x] フィルター（タイプ、未読のみ）が動作する
- [x] ページネーションが動作する
- [x] COORDINATION_LOG に記載
- [x] status.md に記録

