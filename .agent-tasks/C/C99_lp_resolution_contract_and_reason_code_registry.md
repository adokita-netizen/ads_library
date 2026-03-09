# C99: LP Resolution Contract & Reason Code Registry

## 優先度: 🅰️ A（クリティカル）

## 目的
- LP 遷移先情報と失敗理由コードを API レベルで統一し、B/A が追加推測なしで使えるようにする

## 対象ファイル
- `backend/app/api/endpoints/ads.py`
- `backend/app/api/endpoints/media.py`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装タスク
1. `lp_info` に `resolved_url / redirect_chain / final_domain / http_status` を追加する契約を定義
2. `lp_status` の語彙を固定する
   - `alive`
   - `redirect`
   - `dead`
   - `unreachable`
   - `unresolved`
3. `missing_reasons / skipped_reasons` を共通辞書化する
4. API 契約書にサンプルレスポンスを追加する

## 完了条件
- [ ] LP系レスポンスが frontend と監査で共通利用できる
- [ ] reason code の二重定義がなくなる
