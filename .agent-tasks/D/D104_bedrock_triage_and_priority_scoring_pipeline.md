# D104: Bedrock Triage and Priority Scoring Pipeline

## 優先度
- `P0`

## 目的
- Bedrock を使って日本語広告を triage し、商材分類と actual metrics 取得優先度を決める

## 対象
- `backend/app/services/ai/`
- `backend/app/tasks/ops_tasks.py`
- `backend/app/tasks/mlops_tasks.py`
- `backend/scripts/`
- `backend/tests/`

## 実装タスク
1. Bedrock に渡す入力を整理する
   - `title`
   - `description`
   - `advertiser_name`
   - `brand_name`
   - `destination_domain`
   - `LP signals`
   - `OCR / transcript`
2. 出力として以下を保存する
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
3. `JP only` を通過した広告だけに Bedrock triage をかける
4. high priority 広告を `actual metrics enrichment queue` に送る
5. ambiguous / low confidence のみ `manual review queue` に送る
6. rule-based で十分な広告は AI をスキップする

## 完了条件
- [ ] Bedrock が商材分類だけでなく priority scoring まで返す
- [ ] actual metrics を取りに行く順番が自動化される
- [ ] review queue が high-value ambiguity に絞られる
