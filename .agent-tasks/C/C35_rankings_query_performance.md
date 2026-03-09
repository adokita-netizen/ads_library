# C35: ランキングAPIクエリ最適化

## 問題
- `rankings.py` のレスポンスが全フィールド返却 → 不要データ転送でレイテンシ増大
- フォールバッククエリが N+1 問題を含む
- ページネーション未対応 → 全件取得

## 対象ファイル
- `backend/app/api/endpoints/rankings.py`

## 修正

### 1. レスポンスフィールドの選択的返却
```python
# 必要カラムのみ SELECT
query = select(
    Ad.id, Ad.ad_id, Ad.page_name, Ad.snapshot_url,
    Ad.ad_metadata
).where(...)
```

### 2. ページネーション追加
```python
@router.get("/rankings")
async def get_rankings(
    limit: int = Query(default=50, le=200),
    offset: int = Query(default=0, ge=0),
    # ... existing params
):
    query = query.limit(limit).offset(offset)
    total = await session.scalar(select(func.count()).select_from(subq))
    return {"items": results, "total": total, "limit": limit, "offset": offset}
```

### 3. フォールバッククエリの最適化
```python
# N+1 を回避: JOIN で一括取得
query = (
    select(Ad)
    .options(selectinload(Ad.metrics))
    .where(Ad.ad_metadata["hit_level"].as_string().in_(["S", "A", "B"]))
    .order_by(Ad.ad_metadata["latest_hit_score"].as_float().desc())
    .limit(limit)
)
```

## 制約
- `rankings.py` のみ修正
- 既存のレスポンス構造にページネーション情報を追加（既存フィールドは維持）
