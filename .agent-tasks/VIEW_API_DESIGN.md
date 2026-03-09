# API設計レビュー視点 — REST API の品質・一貫性・改善ポイント

## 現在のAPI構成

```
/api/v1/
  /auth/           (4 endpoints)   ← 認証
  /ads/            (16 endpoints)  ← 広告CRUD
  /campaigns/      (7 endpoints)   ← キャンペーン
  /creative/       (8 endpoints)   ← クリエイティブ生成
  /rankings/       (105+ endpoints)← ★ 最大。分析・ランキング・検索・エクスポート全部入り
  /analytics/      (3 endpoints)   ← 分析
  /meta-marketing/ (36 endpoints)  ← Meta API連携
  /competitive/    (21 endpoints)  ← 競合分析
  /lp-analysis/    (14 endpoints)  ← LP分析
  /media/          (30+ endpoints) ← メディア配信
  /predictions/    (3 endpoints)   ← ML予測
  /notifications/  (7 endpoints)   ← 通知
  /settings/       (9 endpoints)   ← 設定
```

---

## 問題 1: /rankings が全部入りすぎ

### 現状: 105+ エンドポイントが1つのルーターに

本来別ルーターにあるべき機能が全部 `/rankings/` に入っている:

```
/rankings/pro-ranking          ← ランキング (正しい)
/rankings/hit-ads              ← ランキング (正しい)
/rankings/dashboard-summary    ← ダッシュボード → /dashboard/ にすべき
/rankings/export/csv           ← エクスポート → /export/ にすべき
/rankings/smart-autocomplete   ← 検索 → /search/ にすべき
/rankings/search-collections   ← 検索 → /search/ にすべき
/rankings/quick-crawl          ← クロール → /crawl/ にすべき
/rankings/crawl-status         ← クロール → /crawl/ にすべき
/rankings/fresh-ads            ← 広告 → /ads/ にすべき
/rankings/creative-dna/{id}    ← 分析 → /analysis/ にすべき
/rankings/hit-factors          ← 分析 → /analysis/ にすべき
/rankings/scenario-archetypes  ← シナリオ → /scenarios/ にすべき
/rankings/user-preferences     ← ユーザー → /users/ にすべき
/rankings/bookmarks            ← ブックマーク → /bookmarks/ にすべき
/rankings/alerts               ← 通知 → /notifications/ にすべき
```

### 理想的な構成
```
/api/v1/
  /auth/           ← 認証・ユーザー
  /ads/            ← 広告CRUD + 検索
  /rankings/       ← ランキング・スコアリングのみ
  /analysis/       ← クリエイティブDNA、ヒットファクター
  /dashboard/      ← ダッシュボードサマリー
  /search/         ← 検索、オートコンプリート、保存検索
  /export/         ← CSV/JSON/レポートエクスポート
  /crawl/          ← クロール実行・ステータス
  /scenarios/      ← シナリオ生成
  /media/          ← メディア配信
  /bookmarks/      ← ブックマーク・コレクション
  /settings/       ← 設定
```

### 対策
**今は変更しない。** フロントが全て `/rankings/` を呼んでいるため、変更コスト高。
将来、エイリアスルーターを追加して徐々に移行:
```python
# 新パスを追加、旧パスも残す
@router.get("/dashboard/summary")  # 新
@router.get("/rankings/dashboard-summary")  # 旧（互換性）
async def dashboard_summary():
    ...
```

---

## 問題 2: レスポンス形式の不統一

### パターン A: items + total + page
```json
{
  "items": [...],
  "total": 58,
  "page": 1,
  "per_page": 20
}
```

### パターン B: 配列直接
```json
[
  {"name": "美容", "count": 15},
  {"name": "健康食品", "count": 10}
]
```

### パターン C: ネスト
```json
{
  "genres": [...],
  "total": 5
}
```

### 問題
フロントが3パターン全てを処理する必要がある:
```typescript
// ProRankingView.tsx
const items = data.items || data.genres || data;
```

### 対策（統一レスポンス形式）
```json
// 一覧系は常にこの形式
{
  "data": [...],
  "meta": {
    "total": 58,
    "page": 1,
    "per_page": 20,
    "has_next": true
  }
}

// 単一オブジェクト
{
  "data": {...}
}

// エラー
{
  "error": {
    "code": "NOT_FOUND",
    "message": "Ad not found",
    "detail": "ad_id=999 does not exist"
  }
}
```

---

## 問題 3: フィールド命名の不統一

### snake_case vs camelCase
```
バックエンド: hit_score, ad_id, created_at (snake_case) ← Python標準
フロント: hitScore, adId, createdAt (camelCase) ← JS標準
```

**対策**: Pydantic の `alias_generator` で自動変換
```python
from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

class AdResponse(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
    )
    ad_id: int
    hit_score: float
    # → JSON: {"adId": 1, "hitScore": 72.5}
```

---

## 問題 4: エラーハンドリング

### 現状
- 一部のエンドポイントは500を返す（未処理例外）
- 一部は `{"detail": "Not found"}` を返す
- 一部は空配列 `[]` を返す

### 統一エラーレスポンス
```python
# 標準エラーハンドラー
@app.exception_handler(HTTPException)
async def http_exception_handler(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": STATUS_CODES.get(exc.status_code, "UNKNOWN"),
                "message": exc.detail,
            }
        }
    )

STATUS_CODES = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    422: "VALIDATION_ERROR",
    429: "RATE_LIMITED",
    500: "INTERNAL_ERROR",
}
```

---

## 問題 5: バージョニング

### 現状
- `/api/v1/` でバージョニング済み
- v2 は存在しない

### 将来の考慮
- 破壊的変更（レスポンス形式統一等）は `/api/v2/` で
- v1 は一定期間維持（フロント移行期間）
- Content negotiation (`Accept` ヘッダー) も検討

---

## 問題 6: 認証の一貫性

### 確認すべき
- 全エンドポイントに `Depends(get_current_user)` が掛かっているか
- パブリックエンドポイント（ヘルスチェック等）は明示的に認証除外

### 特に危険なエンドポイント
```
DELETE /rankings/search-collections/{id}  ← 認証必須
POST   /rankings/quick-crawl              ← 認証必須（リソース消費）
GET    /rankings/export/csv               ← 認証必須（データ流出）
POST   /settings/api-keys                 ← 認証必須（キー設定）
```

---

## 問題 7: Rate Limiting

### 推奨設定
```
/auth/login:        10 req/min (ブルートフォース防止)
/rankings/quick-crawl: 5 req/min (リソース制御)
/export/*:          10 req/min (データ流出防止)
/creative/generate: 20 req/min (API コスト制御)
一般 API:           100 req/min
```

---

## APIドキュメント

### 現状
FastAPI の自動ドキュメント:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### 問題
- 105+ エンドポイントが1つのグループに → 見づらい
- タグ付けが不十分

### 対策
```python
router = APIRouter(prefix="/rankings", tags=["Rankings"])

# さらに細分化
@router.get("/pro-ranking", tags=["Rankings", "Pro Database"])
@router.get("/export/csv", tags=["Rankings", "Export"])
@router.get("/smart-autocomplete", tags=["Rankings", "Search"])
```
