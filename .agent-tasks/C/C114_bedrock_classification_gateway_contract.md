# C114: Bedrock Classification Gateway Contract

## 優先度
- `P0`

## 目的
- Bedrock を使った分類結果を backend 内で扱いやすい形に標準化する

## 対象
- `backend/app/services/ai/`
- `backend/app/api/endpoints/`
- `backend/tests/`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装タスク
1. Bedrock classification response の正規 shape を決める
   - `language`
   - `product_category`
   - `topic_label`
   - `confidence`
   - `reasons`
   - `model_name`
   - `classified_at`
2. timeout / fallback / partial failure 時の contract を決める
3. `rule-based fallback` と `bedrock result` の優先順を固定する
4. fixture と contract test を作る

## 完了条件
- [ ] Bedrock の結果 shape が固定される
- [ ] 失敗時フォールバックの契約がある
- [ ] D と B が同じ語彙を使える
