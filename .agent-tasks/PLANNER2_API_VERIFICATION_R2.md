# Planner 2: API VERIFICATION — Round 2
# 担当: Agent C (スコアリング・ランキングAPI)
# 更新: 2026-03-01

## ★ Round 1 完了サマリー ★

### Agent C 完了分 (C1-C37 全完了!)
- [x] C1-C9: メディアURL, ヒット判定, 分析API, レスポンス統合, トレンド, データ精度, サムネイル, パターン, リアルタイムクロール
- [x] C10-C25: 本番API, 高度分析, 通知, 検索, AI分析, Lambda, レポート, 精度, ProRanking, シナリオ, フィルタ, レポート&アラート, ベンチマーク, 設定, 類似/カレンダー, Webhook/バルク
- [x] C26-C37: クリエイティブインテリジェンス, 分析&インサイト, リアルタイム&WS, ジャンル分析, 検索&オートコンプリート, メディアパイプライン接続, メディア抽出ステータス, DLQ監視, ECSタスクステータス, ランキングクエリ性能, セキュリティバリデーション, リソースクリーンアップ
- [x] コード品質改修: rankings.py (N+1, ページネーション), ads.py (バリデーション), media.py (リソースリーク), runner.py (タイムアウト)
- 成果: 105+ エンドポイント実装済み, 14,779行の rankings.py

---

## Round 2 タスクマップ

```
C-R2-1 AIチャットAPI (P0) ──→ B43 UI連携
  ↓
C-R2-2 通知API (P0) ──────→ B42 UI連携
  ↓
C-R2-3 外部連携API (P1)

並行:
C-R2-4 N+1解消 (P0/CI)
C-R2-5 ページング上限 (P0/CI)
```

## 新規ファイル作成計画

### C-R2-1: AI Chat
```
新規:
  backend/app/api/endpoints/ai_chat.py
  backend/app/services/ai/__init__.py
  backend/app/services/ai/chat_service.py
  backend/app/services/ai/intent_classifier.py
  backend/app/models/conversation.py

修正:
  backend/app/main.py (ルーター登録)
```

### C-R2-2: Notifications
```
新規:
  backend/app/services/notification_service.py

修正:
  backend/app/api/endpoints/rankings.py (通知エンドポイント追加)
  or 新規: backend/app/api/endpoints/notifications.py
```

### C-R2-3: External Integrations
```
新規:
  backend/app/api/endpoints/integrations.py
  backend/app/services/integrations/__init__.py
  backend/app/services/integrations/slack_notifier.py
  backend/app/services/integrations/webhook_sender.py
  backend/app/services/integrations/csv_exporter.py

修正:
  backend/app/main.py (ルーター登録)
```

## API設計一覧 (Round 2 追加分)

### AI Chat (C-R2-1)
| Method | Path | 説明 |
|--------|------|------|
| POST | /api/v1/ai-chat/message | メッセージ送信 + AI応答 |
| GET | /api/v1/ai-chat/conversations | 会話一覧 |
| GET | /api/v1/ai-chat/conversations/{id} | 会話詳細 |
| DELETE | /api/v1/ai-chat/conversations/{id} | 会話削除 |

### Notifications (C-R2-2)
| Method | Path | 説明 |
|--------|------|------|
| GET | /api/v1/rankings/notifications | 通知一覧 |
| PUT | /api/v1/rankings/notifications/{id}/read | 既読 |
| PUT | /api/v1/rankings/notifications/read-all | 全既読 |
| DELETE | /api/v1/rankings/notifications/{id} | 削除 |
| POST | /api/v1/rankings/alert-rules | ルール作成 |
| GET | /api/v1/rankings/alert-rules | ルール一覧 |
| PUT | /api/v1/rankings/alert-rules/{id} | ルール更新 |
| DELETE | /api/v1/rankings/alert-rules/{id} | ルール削除 |

### Integrations (C-R2-3)
| Method | Path | 説明 |
|--------|------|------|
| POST | /api/v1/integrations/slack/configure | Slack設定 |
| POST | /api/v1/integrations/slack/test | テスト送信 |
| POST | /api/v1/integrations/webhooks | Webhook登録 |
| GET | /api/v1/integrations/webhooks | Webhook一覧 |
| DELETE | /api/v1/integrations/webhooks/{id} | Webhook削除 |
| POST | /api/v1/integrations/scheduled-export | 定期エクスポート |

## Planner 1 → 2 の入力待ち

| Planner 1 タスク | Agent C が待つ内容 | 対応 |
|-----------------|-------------------|------|
| A-R2-2 デルタフィールド | view_count_increase 等のカラム追加 | /pro-ranking レスポンスに含める |
| D-R2-2 動画メタデータ | duration_seconds カラム追加 | スコア計算に動画長を加味 |
| A-R2-6 AlertRule モデル | alert_rules テーブル | C-R2-2 で API 化 |

→ いずれも Agent C は独立して先行開発可能（モデルは自前でも作成可）

## 完了基準 (Round 2 End)

- [ ] AI Chat: 4エンドポイント実装 + E2E動作確認
- [ ] Notifications: 8エンドポイント実装 + 通知生成テスト
- [ ] Integrations: 6エンドポイント実装 + Slack テスト送信成功
- [ ] N+1: 主要5 API の SQL 回数 30%以上削減
- [ ] ページング: 全一覧 API に limit 上限 (100) 設定
- [ ] COORDINATION_LOG: B43/B42 向けの API 仕様を記載
