# Phase 2: Product Enhancement Design Specification

最終更新: 2026-03-01

## 概要
Phase 1 で構築した基盤の上に、ユーザー向け付加価値機能を追加する。
4つの柱: AI対話、通知システム、外部連携、ダッシュボードカスタマイズ。

---

## Pillar 1: AI Chat Interface

### ユーザーストーリー
```
広告運用者として、
「美容ジャンルのヒット広告を分析して」と自然言語で質問すると、
構造化された分析レスポンスが返ってくる。
```

### アーキテクチャ
```
┌─────────────┐    ┌──────────────┐    ┌───────────────┐
│  B: ChatUI  │───→│  C: ChatAPI  │───→│ Claude/GPT    │
│  チャット窓  │←───│  インテント   │←───│ (optional)    │
│  履歴表示   │    │  分類・応答   │    │               │
└─────────────┘    └──────────────┘    └───────────────┘
                         │
                         ▼
                   ┌──────────────┐
                   │  DB: 会話    │
                   │  conversations│
                   │  messages    │
                   └──────────────┘
```

### インテント分類

| インテント | トリガーキーワード | 処理内容 |
|-----------|-------------------|---------|
| analyze_ad | 「この広告を分析」「ADxxxを見て」 | 単一広告のスコア・DNA分析 |
| analyze_genre | 「美容ジャンル」「ヒット傾向」 | ジャンル横断分析 |
| compare_ads | 「比較して」「AとBの違い」 | 2-4件の広告比較 |
| find_trends | 「トレンド」「急上昇」 | 直近トレンド抽出 |
| suggest_creative | 「クリエイティブ案」「改善提案」 | 勝ちパターンベースの提案 |

### DB テーブル
```sql
CREATE TABLE conversations (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100),
    title VARCHAR(200),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE messages (
    id SERIAL PRIMARY KEY,
    conversation_id INTEGER REFERENCES conversations(id),
    role VARCHAR(20) NOT NULL,  -- 'user' | 'assistant'
    content TEXT NOT NULL,
    intent VARCHAR(50),
    structured_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

### API エンドポイント
- `POST /api/v1/ai-chat/message` — メッセージ送信
- `GET /api/v1/ai-chat/conversations` — 会話一覧
- `GET /api/v1/ai-chat/conversations/{id}` — 会話詳細
- `DELETE /api/v1/ai-chat/conversations/{id}` — 会話削除

### Frontend コンポーネント
- `AIChatPanel.tsx` — チャット窓（右サイドバーまたはモーダル）
- `ChatMessage.tsx` — メッセージバブル（マークダウン対応）
- `ChatHistory.tsx` — 過去の会話一覧
- `QuickActions.tsx` — ワンクリック分析ボタン

---

## Pillar 2: Notification System

### ユーザーストーリー
```
広告運用者として、
新しいHIT広告が検出されたとき、
ダッシュボード上でリアルタイム通知を受け取る。
```

### アーキテクチャ
```
┌──────────────┐    ┌──────────────┐    ┌───────────────┐
│ A: AlertEngine│───→│ C: NotifyAPI │───→│  B: NotifyUI  │
│ ルール評価   │    │  通知CRUD    │    │  ベルアイコン  │
│ 条件判定     │    │  アラートルール│    │  通知一覧     │
└──────────────┘    └──────────────┘    └───────────────┘
                         │
                         ▼
                   ┌──────────────┐
                   │  DB: 通知    │
                   │  notifications│
                   │  alert_rules │
                   └──────────────┘
```

### アラートルール種別

| 種別 | 条件 | 例 |
|------|------|-----|
| score_threshold | hit_score >= X | 「スコア60以上の新広告」 |
| score_change | |delta| >= X | 「スコアが20以上変動した広告」 |
| new_hit | hit_level IN (...) | 「新しい大HIT広告」 |
| data_quality | quality_score < X | 「データ品質が低下した」 |
| crawl_complete | crawl finished | 「クロール完了: X件取得」 |

### DB テーブル
```sql
CREATE TABLE notifications (
    id SERIAL PRIMARY KEY,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(200) NOT NULL,
    message TEXT,
    is_read BOOLEAN DEFAULT FALSE,
    metadata JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE alert_rules (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    condition_type VARCHAR(50) NOT NULL,
    condition_value JSONB NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE alert_history (
    id SERIAL PRIMARY KEY,
    rule_id INTEGER REFERENCES alert_rules(id),
    triggered_at TIMESTAMP DEFAULT NOW(),
    matched_ads JSONB,
    notification_id INTEGER REFERENCES notifications(id)
);
```

### 通知フロー
1. バッチジョブ完了時に AlertEngine が全ルールを評価
2. 条件一致するルールについて通知レコードを作成
3. フロントエンドが 60 秒間隔でポーリング
4. 未読通知がある場合、ベルアイコンにバッジ表示
5. クリックでドロップダウン表示、既読マーク

---

## Pillar 3: External Integration

### ユーザーストーリー
```
広告運用者として、
HIT広告が検出されたとき Slack に通知が飛び、
週次レポートがメールで自動送信される。
```

### 対応チャネル

| チャネル | 実装方式 | 優先度 |
|---------|---------|--------|
| Slack | Incoming Webhook | P1 |
| Webhook | HMAC 署名付き POST | P1 |
| CSV Export | スケジュール実行 | P1 |
| Email | 将来対応 | P2 |
| LINE | 将来対応 | P3 |

### Slack 連携
```python
# 設定: POST /api/v1/integrations/slack/configure
{
    "webhook_url": "https://hooks.slack.com/services/...",
    "channel": "#ad-alerts",
    "events": ["new_hit", "crawl_complete", "score_change"]
}

# 通知メッセージ例
{
    "text": "🎯 新しいHIT広告を検出しました",
    "blocks": [
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": "*美容サプリ* (score: 78)\nジャンル: 美容 | 配信日数: 14日"
            }
        }
    ]
}
```

### Webhook 配信
```python
# 登録: POST /api/v1/integrations/webhooks
{
    "url": "https://example.com/webhook",
    "secret": "your-secret-key",
    "events": ["new_hit", "score_change"]
}

# 配信ヘッダー
X-VAAP-Signature: sha256=HMAC(secret, body)
X-VAAP-Event: new_hit
X-VAAP-Delivery: uuid
```

---

## Pillar 4: Dashboard Customization

### ユーザーストーリー
```
広告運用者として、
自分だけのダッシュボードレイアウトを保存し、
次回アクセス時に自動で復元される。
```

### 機能一覧

| 機能 | 実装方式 | 担当 |
|------|---------|------|
| セーブドビュー | localStorage + API | B + C |
| クイックフィルター | URL searchParams | B |
| カラムカスタマイズ | localStorage | B |
| ウィジェット配置 | drag & drop | B |
| テーマ切替 | dark/light + system | B |

### セーブドビュー
```typescript
interface SavedView {
  id: string;
  name: string;
  filters: {
    genre?: string;
    platform?: string;
    scoreRange?: [number, number];
    dateRange?: { from: string; to: string };
    hookTypes?: string[];
    searchText?: string;
  };
  sort: { field: string; order: 'asc' | 'desc' };
  columns: string[];
  createdAt: string;
}
```

---

## 実装スケジュール

### Wave 1 (Round 2 タスクとして実行)
- C-R2-1: AI Chat API (バックエンド)
- C-R2-2: Notification API (バックエンド)
- B-R2-5: Onboarding (フロントエンド)
- B-R2-6: Notification Center (フロントエンド)

### Wave 2 (Round 2 後半)
- C-R2-3: External Integration (バックエンド)
- A-R2-6: Alert Engine (バックエンド)
- B43: AI Chat Interface (フロントエンド)
- B44: Dashboard Customization (フロントエンド)

### Wave 3 (Round 3)
- Multi-tenant 対応
- ML ベースの予測モデル統合
- リアルタイム WebSocket 通知

---

## 技術選定

| 技術 | 採用理由 | 代替案 |
|------|---------|--------|
| ルールベース AI | LLM コスト削減、決定論的 | Claude API 直接 |
| ポーリング (60s) | WebSocket のインフラ不要 | Server-Sent Events |
| HMAC 署名 | Webhook のセキュリティ標準 | JWT |
| localStorage | サーバー不要のビュー保存 | DB 保存 |
| Redis 分散ロック | バッチジョブの排他制御 | DB advisory lock |
