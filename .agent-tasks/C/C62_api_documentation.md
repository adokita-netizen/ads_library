# C62: API仕様書（OpenAPI/Swagger）整備

## 優先度: 🅱️ B（重要）

## 問題
- FastAPIはOpenAPIスキーマを自動生成するが、完全性が不明
- レスポンスモデル未定義のエンドポイントがある可能性
- フロントエンド開発者（Agent B）がAPI仕様を把握しづらい

## 対象ファイル
- `backend/app/api/endpoints/` 配下全エンドポイント
- `backend/app/schemas/` 配下（Pydanticモデル）
- `backend/app/main.py`（OpenAPI設定）

## タスク

### Task 1: 現状のOpenAPIスキーマ確認
- `/docs` (Swagger UI) の動作確認
- `/openapi.json` のスキーマ取得と分析
- レスポンスモデル未定義のエンドポイント特定

### Task 2: Pydanticレスポンスモデル追加
- 各エンドポイントに `response_model` を設定
- 共通エラーレスポンスモデル定義
```python
class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
    error_code: Optional[str] = None
```

### Task 3: APIドキュメント強化
- 各エンドポイントに `summary` と `description` を追加
- リクエスト/レスポンス例を追加
- タグによるグループ分け

### Task 4: API仕様書エクスポート
- `openapi.json` をリポジトリにコミット
- API_CONTRACT_REGISTRY.md との整合性確認

## 完了条件
- [ ] 全エンドポイントに `response_model` が設定されている
- [ ] `/docs` でSwagger UIが正常に表示される
- [ ] リクエスト/レスポンス例が全エンドポイントにある
- [ ] `openapi.json` がリポジトリに含まれている

## 連携
- Agent B (B64): APIスキーマに基づいてフロントエンド型定義を自動生成可能に
- API_CONTRACT_REGISTRY.md を更新
