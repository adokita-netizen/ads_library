# C-R2-5: Pagination Limits & Timeout Policy (CI-014 + CI-052)
# 優先度: P0 | 前提: なし | ブロック: なし (並行可)

## 目的
全一覧APIに limit 上限を設定し、大量データリクエストによるOOMを防ぐ。
エンドポイント別のタイムアウト方針を明文化する。

## 対象ファイル
- `backend/app/api/endpoints/rankings.py` (修正)

## 実装

### Step 1: 共通バリデータ
```python
# rankings.py の冒頭に追加
MAX_PAGE_SIZE = 100
DEFAULT_PAGE_SIZE = 20

def validate_pagination(page: int, per_page: int) -> tuple[int, int]:
    """ページネーションパラメータのバリデーション"""
    if page < 1:
        raise HTTPException(400, "page must be >= 1")
    if per_page < 1:
        raise HTTPException(400, "per_page must be >= 1")
    if per_page > MAX_PAGE_SIZE:
        raise HTTPException(400, f"per_page must be <= {MAX_PAGE_SIZE}")
    return page, per_page
```

### Step 2: 全一覧エンドポイントに適用
```python
# 以下の全エンドポイントで per_page/limit に上限チェックを追加:
# - /pro-ranking
# - /hit-ads
# - /notifications
# - /alert-rules
# - /search
# - /similar/{ad_id}
# - /advertiser-detail
# - /conversations (ai-chat)
# - /export/csv (行数上限)
# - /export/json (行数上限)

# パターン:
@router.get("/pro-ranking")
async def pro_ranking(
    page: int = Query(1, ge=1),
    per_page: int = Query(DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
    ...
):
    page, per_page = validate_pagination(page, per_page)
    ...
```

### Step 3: エクスポートの行数上限
```python
MAX_EXPORT_ROWS = 10000

@router.get("/export/csv")
async def export_csv(
    limit: int = Query(MAX_EXPORT_ROWS, ge=1, le=MAX_EXPORT_ROWS),
    ...
):
    ...
```

### Step 4: タイムアウト方針書
各エンドポイントカテゴリのタイムアウトを明文化:

| カテゴリ | タイムアウト | リトライ | 備考 |
|---------|-----------|---------|------|
| 一覧取得 (GET) | 15s | クライアント側で1回 | ページネーション必須 |
| 詳細取得 (GET /{id}) | 10s | クライアント側で1回 | |
| 検索 (GET /search) | 20s | なし | LIKE検索含む |
| 集計 (GET /dashboard-summary) | 30s | なし | 全件集計 |
| エクスポート (GET /export) | 60s | なし | 大量データ |
| クロール (POST /quick-crawl) | 120s | なし | 外部API呼び出し |
| 分析 (POST /compute-rankings) | 300s | なし | 全件再計算 |
| AI Chat (POST /message) | 30s | なし | |

## 完了条件
- [x] 全一覧APIに per_page 上限 (MAX_PAGE_SIZE=100) が設定されている
- [x] 上限超過時に 400 Bad Request が返る
- [x] エクスポートに行数上限が設定されている
- [x] タイムアウト方針がドキュメント化されている
- [x] status.md に記録
