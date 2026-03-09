# C97: Bulk Download Contract & LP Info Alignment

## 優先度: 🅰️ A（クリティカル）

## 目的
- B が安定表示できるよう、bulk download 結果と LP 情報契約を固定する

## 対象ファイル
- `backend/app/api/endpoints/media.py`
- `backend/app/api/endpoints/ads.py`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装タスク
1. `/media/bulk-download` に `skipped_ids` と `requested_count` を追加
2. `/ads/{id}/media` の `lp_info` 契約を `API_CONTRACT_REGISTRY.md` に明記
3. `media_status.missing_reasons` の標準値を固定
4. UIが追加推測なしで使えるレスポンス例を記載

## 完了条件
- [ ] bulk-download の結果が UI でそのまま使える
- [ ] lp_info/media_status 契約が設計書に明記される
- [ ] missing reason の語彙が固定される

