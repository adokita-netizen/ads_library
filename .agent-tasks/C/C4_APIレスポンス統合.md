# Agent C 次フェーズ: score_breakdown をhit-adsレスポンスに統合

## 概要
C3で作成した分析APIの `score_breakdown` データを、既存の `/rankings/hit-ads` と `/rankings/products` のレスポンスに直接含める。
これによりフロントエンドが追加APIコールなしでスコア内訳を表示できる。

## 必ず最初に読むファイル
```
backend/app/api/endpoints/rankings.py  ← 修正対象（既存エンドポイント）
backend/app/services/ranking/ranking_service.py  ← compute_hit_score関数
```

---

## タスク1: /rankings/hit-ads レスポンスに score_breakdown 追加

### 現状
`/rankings/hit-ads` はProductRankingベースだが、`score_breakdown` はProductRankingの `extra_metadata` にしか入っていない。
フォールバックパス（_fallback_hit_ads）ではcompute_hit_scoreを呼んで4値返しているが、breakdownをレスポンスに含めていない。

### 修正方針
1. ProductRankingベースのパス: `r.extra_metadata.get("score_breakdown", {})` を各itemに追加（既存で一部実装済み）
2. フォールバックパス（`_fallback_hit_ads`）: `compute_hit_score()` の返り値 `breakdown` をレスポンスに含める
3. 各レスポンスアイテムに `"score_breakdown": {...}` フィールドを追加

### レスポンス形式の変更
```json
{
  "ad_id": 123,
  "hit_score": 78.5,
  "score_breakdown": {
    "longevity": 35.0,
    "spend": 15.0,
    "active_bonus": 20.0,
    "creative": 7.0,
    "trend": 3.0
  },
  ...既存フィールド
}
```

---

## タスク2: /rankings/products レスポンスにも統合

ProductRankingレコードがある場合は `extra_metadata.score_breakdown` を、
ない場合は `compute_hit_score()` を呼んで `breakdown` を含める。

---

## タスク3: _fallback_ad_list の改善

`_fallback_ad_list()` でも全広告に対して score_breakdown を含める。
現在はcompute_hit_scoreを呼んでいるのでbreakdownは取得済み → レスポンスに追加するだけ。

---

## タスク4: FastAPI deprecation warning の修正

`regex=` パラメータが deprecated → `pattern=` に変更。

```python
# Before
period: str = Query("weekly", regex="^(daily|weekly|monthly)$")

# After
period: str = Query("weekly", pattern="^(daily|weekly|monthly)$")
```

全箇所を修正する。

---

## コンフリクト防止ルール
- `INSTRUCTIONS.md` を厳守
- 修正するファイル: `backend/app/api/endpoints/rankings.py` のみ
- `frontend/` は一切触らない
- 既存のAPIレスポンス構造を壊さない（フィールド追加のみ）
- テストとして uvicorn 起動時にインポートエラーがないことを確認

## 完了条件
- `/rankings/hit-ads` のレスポンスに `score_breakdown` が含まれる
- `/rankings/products` のレスポンスに `score_breakdown` が含まれる
- FastAPI deprecation warning が消える
- 既存の全エンドポイントが正常動作する
