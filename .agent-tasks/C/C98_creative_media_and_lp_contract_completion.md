# C98: Creative Media & LP Contract Completion

## 優先度: 🅰️ A（クリティカル）

## 目的
- B が追加推測なしで UI を組めるように、CR/DL/LP 系レスポンス契約を完成させる

## 対象ファイル
- `backend/app/api/endpoints/ads.py`
- `backend/app/api/endpoints/media.py`
- `backend/app/schemas/`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装タスク
1. `/ads/{id}/media` の `media_status` を `viewable / downloadable / has_lp / missing_reasons` で固定
2. `/ads/{id}/media` の `lp_info` を `destination_url / domain / destination_type / lp_status / lp_score / resolved_url` まで固定
3. `/media/bulk-download` に `requested_count / downloaded_count / skipped_ids / skipped_reasons` を揃える
4. `missing_reasons` と `skipped_reasons` の語彙を統一する
   - `missing_creative`
   - `download_unavailable`
   - `snapshot_only`
   - `lp_missing`
   - `lp_unresolved`
5. `API_CONTRACT_REGISTRY.md` にレスポンス例を追記し、frontend がそのまま利用できるようにする

## 完了条件
- [ ] media_status / lp_info / bulk-download の契約が固定される
- [ ] frontend 側の追加推測なしで表示できる
- [ ] DL失敗理由とLP取得状態の語彙が統一される

## 制約
- Agent D の回収ロジックは変更しない
- Agent B が必要とする表示単位に寄せる
