# 通知システム設計視点 — ユーザーに適切なタイミングで情報を届ける

## なぜ通知が必要か

- 新しいヒット広告が発見された → すぐに知りたい
- クロールが完了した → 結果を確認したい
- Meta APIトークンが期限切れ間近 → 事前に対処したい
- エクスポートが完了した → ダウンロードしたい

---

## 通知チャネル設計

### 3段階の通知チャネル

```
Level 1: アプリ内通知（常に）
  → トースト、バッジ、通知パネル

Level 2: ブラウザ通知（オプトイン）
  → Web Push Notification

Level 3: 外部通知（将来）
  → メール、Slack、LINE
```

---

## Level 1: アプリ内通知

### 通知の種類

```typescript
type NotificationType =
  | 'hit_ad_found'        // 新しいヒット広告発見
  | 'crawl_complete'      // クロール完了
  | 'score_updated'       // スコア再計算完了
  | 'export_ready'        // エクスポートファイル準備完了
  | 'media_extracted'     // メディア抽出完了
  | 'token_expiring'      // トークン期限切れ警告
  | 'token_expired'       // トークン期限切れ
  | 'system_error'        // システムエラー
  | 'data_quality_alert'  // データ品質アラート

interface Notification {
  id: string;
  type: NotificationType;
  title: string;
  message: string;
  severity: 'info' | 'warning' | 'error' | 'success';
  timestamp: string;
  read: boolean;
  action_url?: string;   // クリック時の遷移先
  metadata?: Record<string, any>;
}
```

### トースト通知コンポーネント

```typescript
// components/common/ToastNotification.tsx

interface ToastProps {
  notification: Notification;
  onDismiss: () => void;
  onAction: () => void;
}

// 自動消去: info=5秒, success=3秒, warning=10秒, error=手動消去
const AUTO_DISMISS: Record<string, number> = {
  info: 5000,
  success: 3000,
  warning: 10000,
  error: 0,  // 手動消去のみ
};
```

### 通知パネル

```
┌─────────────────────────────────────┐
│ 🔔 通知 (3)                    全て既読 │
├─────────────────────────────────────┤
│ 🟢 新しいヒット広告を5件発見          │
│    美容ジャンルで大ヒット広告...      │
│    2分前                    → 詳細を見る │
├─────────────────────────────────────┤
│ 🔵 クロール完了                       │
│    「サプリ」で25件の広告を取得       │
│    15分前                   → 結果を見る │
├─────────────────────────────────────┤
│ 🟡 Meta APIトークンが7日で期限切れ   │
│    更新してください                   │
│    1時間前                  → 設定へ    │
└─────────────────────────────────────┘
```

---

## バックエンド: 通知API

### エンドポイント設計

```
GET    /api/v1/notifications              → 通知一覧
GET    /api/v1/notifications/unread-count → 未読数
PATCH  /api/v1/notifications/{id}/read    → 既読にする
POST   /api/v1/notifications/read-all     → 全て既読
DELETE /api/v1/notifications/{id}         → 削除
```

### 通知の生成トリガー

```python
# app/services/notification_service.py

class NotificationService:
    def __init__(self, db: Session):
        self.db = db

    def create(self, type: str, title: str, message: str,
               severity: str = "info", action_url: str = None):
        notification = Notification(
            type=type,
            title=title,
            message=message,
            severity=severity,
            action_url=action_url,
            created_at=datetime.utcnow(),
            read=False,
        )
        self.db.add(notification)
        self.db.commit()
        return notification

# クロール完了時
async def on_crawl_complete(keyword, ads_found, new_ads, hits):
    svc = NotificationService(db)
    if hits > 0:
        svc.create(
            type="hit_ad_found",
            title=f"新しいヒット広告を{hits}件発見",
            message=f"「{keyword}」のクロールで{ads_found}件取得、{hits}件がヒット",
            severity="success",
            action_url="/pro-ranking?sort=hit_score&keyword=" + keyword
        )
    else:
        svc.create(
            type="crawl_complete",
            title="クロール完了",
            message=f"「{keyword}」で{ads_found}件取得（新規{new_ads}件）",
            severity="info",
        )
```

---

## リアルタイム通知（将来）

### Server-Sent Events (SSE)

```python
# app/api/endpoints/notifications.py
from fastapi import Request
from sse_starlette.sse import EventSourceResponse

@router.get("/notifications/stream")
async def notification_stream(request: Request):
    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            # 新しい通知をチェック
            notifications = get_new_notifications(last_check)
            if notifications:
                yield {
                    "event": "notification",
                    "data": json.dumps([n.dict() for n in notifications])
                }
            await asyncio.sleep(10)  # 10秒ごとにポーリング

    return EventSourceResponse(event_generator())
```

### フロントエンドの SSE 接続

```typescript
// hooks/useNotifications.ts
function useNotifications() {
  const [notifications, setNotifications] = useState<Notification[]>([]);

  useEffect(() => {
    const eventSource = new EventSource('/api/v1/notifications/stream');

    eventSource.addEventListener('notification', (event) => {
      const newNotifications = JSON.parse(event.data);
      setNotifications(prev => [...newNotifications, ...prev]);
      // トースト表示
      newNotifications.forEach(n => showToast(n));
    });

    return () => eventSource.close();
  }, []);

  return notifications;
}
```

### Lambda での SSE の制約

```
問題: Lambda は長時間接続を保持できない（最大15分）
      API Gateway WebSocket は追加コスト

代替案:
  1. ポーリング: 30秒ごとに GET /notifications/unread-count
     → 最もシンプル、Lambda と相性良い
     → 最大30秒の遅延

  2. CloudFront + Lambda@Edge で SSE
     → 複雑だが追加コスト少

  3. API Gateway WebSocket
     → リアルタイムだがコスト増

推奨: Phase 1 はポーリング、需要があればWebSocket
```

---

## 通知テンプレート

### hit_ad_found
```
タイトル: 🎯 新しいヒット広告を{count}件発見
メッセージ: {genre}ジャンルで{level}広告が見つかりました。スコア: {score}
アクション: PRO DATABASEで確認 →
```

### crawl_complete
```
タイトル: ✅ クロール完了
メッセージ: 「{keyword}」で{total}件取得（新規{new}件、更新{updated}件）
アクション: 結果を見る →
```

### token_expiring
```
タイトル: ⚠️ Meta APIトークンが{days}日で期限切れ
メッセージ: トークンを更新しないとクロールが停止します
アクション: 設定で更新 →
```

### export_ready
```
タイトル: 📥 エクスポート完了
メッセージ: {format}ファイル（{count}件, {size}）のダウンロード準備完了
アクション: ダウンロード →
```

### system_error
```
タイトル: ❌ システムエラー
メッセージ: {endpoint}でエラーが発生しました: {error_message}
アクション: 詳細を見る →
```

---

## 通知設定（ユーザーカスタマイズ）

```typescript
interface NotificationPreferences {
  // 通知タイプごとの有効/無効
  hit_ad_found: boolean;      // デフォルト: true
  crawl_complete: boolean;    // デフォルト: true
  score_updated: boolean;     // デフォルト: false
  export_ready: boolean;      // デフォルト: true
  token_expiring: boolean;    // デフォルト: true
  system_error: boolean;      // デフォルト: true

  // チャネル設定
  browser_push: boolean;      // デフォルト: false
  sound: boolean;             // デフォルト: false

  // 通知頻度
  batch_interval: number;     // 分単位、0=即時
}
```

---

## DBスキーマ

```sql
CREATE TABLE notifications (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT,
    severity VARCHAR(20) DEFAULT 'info',
    read BOOLEAN DEFAULT FALSE,
    action_url VARCHAR(500),
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP  -- 自動削除用
);

CREATE INDEX idx_notifications_unread ON notifications (read) WHERE read = FALSE;
CREATE INDEX idx_notifications_created ON notifications (created_at DESC);

-- 30日以上前の通知を自動削除
-- pg_cron or Lambda スケジュールで実行
DELETE FROM notifications WHERE created_at < NOW() - INTERVAL '30 days';
```

---

## 実装優先度

```
[Phase 1] ポーリング + トースト
  1. notifications テーブル作成
  2. 通知作成API + 一覧API
  3. クロール完了時に通知生成
  4. フロントのトースト表示 + ヘッダーバッジ
  → ポーリング間隔: 30秒

[Phase 2] 通知パネル + 設定
  5. 通知パネルUI
  6. 既読管理
  7. 通知設定画面
  8. token_expiring の自動チェック

[Phase 3] リアルタイム
  9. SSE or WebSocket
  10. ブラウザ Push Notification
```
