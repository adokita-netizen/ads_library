# C-R2-1: AI Chat API (C38 Phase 2)
# 優先度: P0 | 前提: なし | ブロック: B43 (AI Chat UI)

## 目的
VAAP内でAIチャットを提供する。広告分析の質問に対してDB内のデータを使って回答する。

## 対象ファイル (全て Agent C 専有)
- 新規: `backend/app/api/endpoints/ai_chat.py`
- 新規: `backend/app/services/ai/chat_service.py`
- 新規: `backend/app/services/ai/intent_classifier.py`
- 新規: `backend/app/models/conversation.py`
- 修正: `backend/app/api/endpoints/__init__.py` (ルーター登録)
- 修正: `backend/app/main.py` (ルーター登録)

## モデル定義

### Conversation モデル
```python
# backend/app/models/conversation.py
from sqlalchemy import Column, Integer, String, DateTime, JSON, Text
from app.core.database import Base
from datetime import datetime

class Conversation(Base):
    __tablename__ = "conversations"

    id = Column(Integer, primary_key=True, index=True)
    title = Column(String(200), default="New Conversation")
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    messages = Column(JSON, default=[])
    # messages: [{ role: "user"|"assistant", content: str, timestamp: str, intent: str|null }]
    metadata = Column(JSON, default={})
```

## APIエンドポイント

### POST /api/v1/ai-chat/message
```python
@router.post("/message")
async def send_message(
    request: ChatMessageRequest,
    db: Session = Depends(get_db)
):
    """
    Request:
    {
        "conversation_id": 1 | null,  // null で新規会話
        "message": "美容ジャンルのHIT広告の共通点は？"
    }

    Response:
    {
        "conversation_id": 1,
        "response": {
            "message": "美容ジャンルのHIT広告には以下の共通点があります...",
            "intent": "analyze_genre",
            "data": { ... },  // 構造化データ（あれば）
            "actions": [
                { "label": "HIT広告一覧を見る", "view": "hit-ads", "params": { "genre": "美容" } },
                { "label": "トレンドを確認", "view": "trend" }
            ],
            "related_ad_ids": [12, 45, 78]
        }
    }
    """
```

### GET /api/v1/ai-chat/conversations
```python
@router.get("/conversations")
async def list_conversations(
    limit: int = Query(20, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """会話一覧（最新順）"""
    # Response: { conversations: [{ id, title, created_at, message_count }], total }
```

### GET /api/v1/ai-chat/conversations/{id}
```python
@router.get("/conversations/{conversation_id}")
async def get_conversation(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    """特定会話の全メッセージ"""
    # Response: { id, title, messages: [...], created_at }
```

### DELETE /api/v1/ai-chat/conversations/{id}
```python
@router.delete("/conversations/{conversation_id}")
async def delete_conversation(
    conversation_id: int,
    db: Session = Depends(get_db)
):
    """会話削除"""
```

## IntentClassifier

```python
# backend/app/services/ai/intent_classifier.py

class IntentClassifier:
    INTENTS = {
        "analyze_ad": ["この広告", "広告を分析", "スコア", "なぜHIT"],
        "analyze_genre": ["ジャンル", "美容", "健康", "ダイエット", "共通点", "パターン"],
        "compare_ads": ["比較", "違い", "どっち", "AとB"],
        "find_trends": ["トレンド", "急上昇", "最近", "伸びている"],
        "suggest_creative": ["提案", "アイデア", "どんな広告", "作りたい"],
        "data_stats": ["何件", "いくつ", "合計", "平均", "統計"],
        "general": [],
    }

    def classify(self, message: str) -> str:
        message_lower = message.lower()
        scores = {}
        for intent, keywords in self.INTENTS.items():
            score = sum(1 for kw in keywords if kw in message_lower)
            scores[intent] = score

        best = max(scores, key=scores.get)
        return best if scores[best] > 0 else "general"
```

## ChatService

```python
# backend/app/services/ai/chat_service.py

class ChatService:
    def __init__(self, session):
        self.session = session
        self.classifier = IntentClassifier()

    async def process_message(self, conversation_id: int | None, message: str) -> dict:
        intent = self.classifier.classify(message)

        # インテント別にDBクエリを実行してデータを取得
        if intent == "analyze_genre":
            data = self._analyze_genre(message)
        elif intent == "data_stats":
            data = self._get_stats()
        elif intent == "find_trends":
            data = self._find_trends()
        elif intent == "analyze_ad":
            data = self._analyze_ad(message)
        else:
            data = None

        # ルールベース応答を生成
        response_text = self._generate_response(intent, data, message)

        # 会話に保存
        conversation = self._save_to_conversation(conversation_id, message, response_text, intent)

        return {
            "conversation_id": conversation.id,
            "response": {
                "message": response_text,
                "intent": intent,
                "data": data,
                "actions": self._suggest_actions(intent, data),
                "related_ad_ids": self._get_related_ads(intent, data),
            }
        }

    def _analyze_genre(self, message: str) -> dict:
        """ジャンル分析: DBからジャンル別の統計を取得"""
        # genre_name を message から抽出
        # SELECT count(*), avg(hit_score), ... FROM ads WHERE category = ?
        ...

    def _get_stats(self) -> dict:
        """全体統計"""
        total = self.session.query(func.count(Ad.id)).scalar()
        hit_count = self.session.query(func.count(Ad.id)).filter(
            Ad.ad_metadata['is_hit'].as_boolean() == True
        ).scalar()
        ...
        return {"total_ads": total, "hit_count": hit_count, ...}

    def _generate_response(self, intent: str, data: dict, message: str) -> str:
        """ルールベースの応答テンプレート"""
        if intent == "data_stats" and data:
            return f"現在DBには{data['total_ads']}件の広告があります。うち{data['hit_count']}件がHIT広告です。"
        elif intent == "analyze_genre":
            return f"...(ジャンル分析結果)..."
        else:
            return "申し訳ありません。もう少し具体的に質問してください。例: 「美容ジャンルのHIT広告の共通点は？」"
```

## ルーター登録
```python
# backend/app/main.py に追加
from app.api.endpoints import ai_chat
app.include_router(ai_chat.router, prefix="/api/v1/ai-chat", tags=["AI Chat"])
```

## マイグレーション
```bash
alembic revision --autogenerate -m "add conversations table"
alembic upgrade head
```

## COORDINATION_LOG に記載
```
[Planner 2 → Planner 3] AI Chat API 実装完了。
- POST /api/v1/ai-chat/message
- GET /api/v1/ai-chat/conversations
- GET /api/v1/ai-chat/conversations/{id}
- DELETE /api/v1/ai-chat/conversations/{id}
レスポンス形式: { conversation_id, response: { message, intent, data, actions, related_ad_ids } }
Agent B は B43 で UI を作成してください。
```

## 完了条件
- [x] Conversation モデルが作成され、テーブルが存在
- [x] 4つのエンドポイントが実装済み
- [x] IntentClassifier が5種のインテントを分類できる
- [x] ルールベース応答が動作する
- [x] 新規会話作成 → メッセージ送信 → 応答受信のE2Eが動作
- [x] COORDINATION_LOG に記載
- [x] status.md に記録

