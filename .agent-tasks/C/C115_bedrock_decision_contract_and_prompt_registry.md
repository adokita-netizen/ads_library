# C115: Bedrock Decision Contract and Prompt Registry

## 優先度
- `P0`

## 目的
- Bedrock の出力を分類結果ではなく意思決定 payload として固定し、prompt/version 追跡を可能にする

## 対象
- `backend/app/services/ai/`
- `backend/app/api/endpoints/`
- `backend/tests/`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装タスク
1. Bedrock decision payload の shape を固定する
   - `language`
   - `product_category`
   - `product_subcategory`
   - `topic_label`
   - `offer_type`
   - `funnel_type`
   - `priority_score`
   - `priority_reason`
   - `review_required`
   - `review_reason`
   - `confidence_band`
   - `model_name`
   - `prompt_version`
   - `classified_at`
2. `rule-based override` と `Bedrock result` の優先順を固定する
3. prompt registry を作り、 `prompt_version` を必ず保存する
4. timeout / partial failure / invalid JSON 時の fallback contract を決める
5. fixture と contract test を追加する

## 完了条件
- [ ] Bedrock decision payload が固定される
- [ ] prompt/version/model の provenance が追跡できる
- [ ] D/B/A が同じ語彙で連携できる
