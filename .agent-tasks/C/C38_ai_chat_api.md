# C38: AI チャット分析API

## 概要
Claude APIを使い、ユーザーの自然言語クエリを広告データ分析に変換して回答するAPIを構築する。
B43のフロントエンド AI チャットUIのバックエンド。

## 背景
VAAPは豊富な分析データを持っているが、ユーザーが必要な情報にたどり着くにはUIを操作する必要がある。
自然言語で「美容ジャンルの勝ちパターンは？」と聞けば即座に分析結果が返る体験は、
競合プロダクトとの圧倒的な差別化要因になる。

## タスク

### Task 1: AI チャットエンドポイント
```python
# backend/app/api/endpoints/ai_chat.py (新規)

@router.post("/chat")
async def chat(request: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    1. ユーザーのメッセージを受け取る
    2. 意図を分類する (intent detection)
    3. 必要なデータをDBから取得する
    4. Claude API にコンテキスト + クエリを送る
    5. 構造化されたレスポンスを返す
    """
```

### Task 2: インテント分類 & データ取得ルーター
```python
# backend/app/services/ai/intent_router.py (新規)

class IntentRouter:
    """ユーザーのメッセージから意図を判定し、必要なデータを収集する"""

    INTENTS = {
        "hit_analysis":    ["ヒット", "HIT", "勝ち", "人気", "スコア高い"],
        "trend_analysis":  ["トレンド", "伸びてる", "急上昇", "最近"],
        "competitor":      ["競合", "ライバル", "他社", "比較"],
        "creative_brief":  ["ブリーフ", "参考に", "パクり", "クリエイティブ"],
        "pattern_analysis":["パターン", "共通点", "特徴", "傾向"],
        "recommendation":  ["おすすめ", "提案", "改善", "アドバイス"],
        "data_query":      ["何件", "一覧", "リスト", "教えて"],
    }

    async def route(self, message: str, context: dict) -> dict:
        """
        Returns: {
            "intent": "hit_analysis",
            "data": { ... },  # DBから取得した関連データ
            "system_prompt": "..."  # Claude用のシステムプロンプト
        }
        """
        intent = self._classify_intent(message)
        data = await self._fetch_data(intent, message, context)
        system_prompt = self._build_system_prompt(intent, data)
        return {"intent": intent, "data": data, "system_prompt": system_prompt}
```

### Task 3: Claude API 統合サービス
```python
# backend/app/services/ai/claude_chat.py (新規)

class ClaudeChatService:
    """Anthropic Claude API との通信を管理する"""

    def __init__(self):
        self.client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        self.model = "claude-sonnet-4-5-20250514"

    async def generate_response(self, user_message: str, system_prompt: str,
                                 context_data: dict) -> dict:
        """
        Claude に質問を送り、構造化されたレスポンスを取得する。

        system_prompt に以下を含める:
        - VAAPのデータ構造の説明
        - 利用可能なデータの要約
        - 回答フォーマットの指定（JSON構造）
        """
        response = self.client.messages.create(
            model=self.model,
            max_tokens=4096,
            system=system_prompt,
            messages=[{"role": "user", "content": user_message}]
        )

        # レスポンスを構造化して返す
        return self._parse_response(response.content[0].text, context_data)

    def _parse_response(self, text: str, context_data: dict) -> dict:
        """
        AIの回答をパースし、リッチデータを付与する。
        - 広告IDが言及されていたら ad オブジェクトを添付
        - 数値データがあったらチャートデータを生成
        """
        return {
            "reply": text,
            "data": {
                "ads": [],       # 関連広告リスト
                "charts": [],    # チャートデータ
                "actions": [],   # 推奨アクション
            }
        }
```

### Task 4: プリセットプロンプト & テンプレート
```python
# backend/app/services/ai/prompt_templates.py (新規)

SYSTEM_PROMPTS = {
    "hit_analysis": """
あなたはVAAP広告分析プラットフォームのAIアドバイザーです。
以下の広告データを元に、ユーザーの質問に日本語で回答してください。

現在のデータ:
- 総広告数: {total_ads}件
- ジャンル分布: {genre_distribution}
- HIT広告数: {hit_count}件

該当広告データ:
{ads_json}

回答形式:
1. 簡潔な要約（2-3文）
2. 具体的なデータポイント（箇条書き）
3. 推奨アクション（あれば）
""",
    # ... 各intentごとにテンプレート
}
```

### Task 5: 会話履歴管理
```python
# backend/app/models/conversation.py (新規)

class Conversation(Base):
    __tablename__ = "conversations"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid4()))
    user_id = Column(Integer, ForeignKey("users.id"))
    title = Column(String(200))  # 最初のメッセージから自動生成
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, onupdate=func.now())

class ConversationMessage(Base):
    __tablename__ = "conversation_messages"
    id = Column(Integer, primary_key=True)
    conversation_id = Column(String(36), ForeignKey("conversations.id"))
    role = Column(String(20))  # "user" or "assistant"
    content = Column(Text)
    data = Column(JSON, nullable=True)  # リッチデータ
    created_at = Column(DateTime, server_default=func.now())
```

## API仕様
```
POST /api/v1/ai/chat
Request:
{
  "message": "美容ジャンルの勝ちパターンを教えて",
  "conversation_id": "uuid" | null,
  "context": {
    "current_view": "pro-database",
    "selected_genre": "美容",
    "selected_ads": [123, 456]
  }
}

Response:
{
  "conversation_id": "uuid",
  "reply": "美容ジャンルのHIT広告を分析しました...",
  "data": {
    "ads": [
      {"id": 123, "title": "美容液ABC", "score": 92, "thumbnail_url": "..."},
    ],
    "charts": [
      {"type": "bar", "title": "フックタイプ分布", "data": {...}}
    ],
    "actions": [
      {"label": "該当広告を一覧で見る", "action": "navigate", "params": {"view": "pro-database", "genre": "美容"}}
    ]
  }
}

GET /api/v1/ai/conversations
GET /api/v1/ai/conversations/{id}/messages
DELETE /api/v1/ai/conversations/{id}
```

## 完了条件
- [x] POST /ai/chat がClaude APIを呼び出して回答を返す
- [x] インテント分類が正しく動作する
- [x] 広告データがコンテキストとしてClaudeに渡される
- [x] 会話履歴がDBに保存される
- [x] 構造化レスポンス（ads, charts, actions）が返される

## 触っていいファイル
- backend/app/api/endpoints/ai_chat.py (新規)
- backend/app/services/ai/ (新規ディレクトリ)
- backend/app/models/conversation.py (新規)
- backend/app/schemas/ai_chat.py (新規)
- backend/app/api/endpoints/__init__.py (ルーター登録)
- migrations/ (Alembic)

## 注意
- ANTHROPIC_API_KEY は backend/app/core/config.py に既に定義済み
- Claude APIのコスト管理: 1リクエストあたりの max_tokens を制限
- レート制限: 1ユーザーあたり 10回/分

