# C112: Real Metrics Contract & Provenance API

## 優先度
- `P0`

## 目的
- 実データ数値を API 契約として固定し、frontend が provenance を安全に表示できるようにする

## 対象
- `backend/app/api/endpoints/rankings.py`
- `backend/app/api/endpoints/ads.py`
- `backend/app/schemas/`
- `backend/tests/`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装タスク
1. 数値系フィールドに以下を標準追加する
   - `metric_source`
   - `metric_status`
   - `freshness_status`
   - `measured_at`
   - `confidence_label`
2. `spend / impressions / reach / lp_score / extract_quality_score` のレスポンス shape を `ads` と `rankings` でそろえる
3. `real / estimated / missing / stale` の reason code を registry に追加する
4. contract test で field の存在、型、fallback を固定する
5. fixture response を B がそのまま使える形で用意する

## 完了条件
- [ ] 実数値 provenance の API 契約が固定される
- [ ] reason code と response 例が registry に残る
- [ ] B の UI が backend 差分で壊れにくくなる

## ハンドオフ
- to B:
  - fixture payload
  - enum 一覧
- from D:
  - source field mapping と freshness ルール
