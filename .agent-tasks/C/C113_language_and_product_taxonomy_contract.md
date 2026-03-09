# C113: Language & Product Taxonomy Contract

## 優先度
- `P0`

## 目的
- 言語判定と商材分類を API 契約として固定する

## 対象
- `backend/app/api/endpoints/rankings.py`
- `backend/app/api/endpoints/ads.py`
- `backend/app/schemas/`
- `backend/tests/`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装タスク
1. 以下の field を標準化する
   - `language`
   - `language_status`
   - `language_confidence`
   - `language_source`
   - `product_category`
   - `product_subcategory`
   - `exclude_from_analysis`
   - `exclude_reason`
2. `unknown` と `non-ja` の meaning を固定する
3. `JP only` フィルタ契約を rankings / search で統一する
4. API registry に response example と reason code を追加する
5. contract tests を追加する

## 完了条件
- [ ] 言語と商材分類の field 名が固定される
- [ ] B が UI で安全に使える
- [ ] D の Bedrock 結果が揺れても契約が壊れない
