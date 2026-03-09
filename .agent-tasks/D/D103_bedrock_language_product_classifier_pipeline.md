# D103: Bedrock Language & Product Classifier Pipeline

## 優先度
- `P0`

## 目的
- Bedrock を使って言語判定、商材分類、トピック補正を行い、分析精度を上げる

## 対象
- `backend/app/services/ai/`
- `backend/app/tasks/ops_tasks.py`
- `backend/app/tasks/mlops_tasks.py`
- `backend/scripts/`
- `backend/tests/`

## 実装タスク
1. Bedrock 呼び出し基盤を用意する
2. 入力に title / description / advertiser / LP domain / OCR を渡す
3. 出力として以下を保存する
   - `language`
   - `product_category`
   - `product_subcategory`
   - `topic_label`
   - `classification_confidence`
   - `classification_reasons`
4. rule-based で十分なケースは Bedrock をスキップしてコストを抑える
5. retry / cooldown / error logging をつける

## 完了条件
- [ ] Bedrock で language + 商材分類 + topic 補正が回る
- [ ] rule-based と組み合わせてコスト最適化される
- [ ] C が使う contract に合わせて保存される
