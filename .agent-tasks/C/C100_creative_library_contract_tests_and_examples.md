# C100: Creative Library Contract Tests & Examples

## 優先度: 🅰️ A（クリティカル）

## 目的
- CR/DL/LP 系エンドポイントの契約をテストで固定し、仕様の後退を防ぐ

## 対象ファイル
- `backend/app/api/endpoints/ads.py`
- `backend/app/api/endpoints/media.py`
- `backend/tests/`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装タスク
1. `/ads/{id}/media` の `media_status / lp_info / download_url` 契約テストを追加
2. `/media/bulk-download` の `requested_count / downloaded_count / skipped_ids / skipped_reasons` 契約テストを追加
3. `snapshot only / downloadable / lp missing / lp resolved` の代表ケース fixture を追加
4. 契約書のレスポンス例とテストケースを一致させる

## 完了条件
- [ ] Creative Library の主要 API 契約がテストで固定される
- [ ] UI が依存するレスポンスが後退しにくくなる
