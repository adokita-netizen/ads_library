# C116: Bedrock Review Queue and Priority API

## 優先度
- `P0`

## 目的
- Bedrock の priority と review 判定を API から安定して扱えるようにする

## 対象
- `backend/app/api/endpoints/rankings.py`
- `backend/app/services/ranking/`
- `backend/tests/`

## 実装タスク
1. `high_priority_actual_metrics` 向け API shape を定義する
2. `review_queue` API を定義する
3. `priority_score`, `review_required`, `review_reason`, `confidence_band` を検索/一覧で返す
4. `rule / ai / manual` の provenance を返す
5. `only_high_priority`, `only_review_required`, `priority_min` などの filter contract を決める
6. response example と contract test を追加する

## 完了条件
- [ ] priority / review の API 契約が固定される
- [ ] frontend が運用ビューを組める
- [ ] actual metrics 優先対象を API で安定取得できる
