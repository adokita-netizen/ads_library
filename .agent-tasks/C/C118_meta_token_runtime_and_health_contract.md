# C118: Meta Token Runtime and Health Contract

## 優先度
- `P0`

## 目的
- Meta token の runtime source, expiry, health を見える化し、期限切れや古い保存値で壊れない契約を作る

## 対象
- `backend/app/services/meta_marketing/token_manager.py`
- `backend/app/api/endpoints/settings.py`
- `backend/app/core/config.py`
- `backend/tests/`

## 実装タスク
1. token source を `db / env / missing` で返す health payload を追加する
2. `expires_at / days_remaining / is_expiring / last_validation_error` を API で返す
3. `DB が env より優先される` 運用を前提に、期限切れ token 検知時の fallback 契約を決める
4. 長期トークン交換の結果 payload を固定する
5. token health の契約テストを追加する

## 完了条件
- [ ] token 状態を API で追える
- [ ] 期限切れ token による silent failure を減らせる
- [ ] D の scheduler と B の表示に必要な項目が揃う
