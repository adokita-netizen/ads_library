# C117: Meta Data Contract and Freshness API

## 優先度
- `P0`

## 目的
- Meta 広告に関する `品質状態 / freshness / provenance` を API 契約として固定する

## 対象
- `backend/app/api/endpoints/`
- `backend/app/services/`
- `backend/tests/`

## 実装タスク
1. Meta 用に `metric_source`, `creative_source`, `lp_source` enum を固定する
2. `real / estimated / missing / stale` の quality 状態を API で返す
3. `last_meta_success_at`, `meta_quality_state`, `meta_recovery_reason` を返す契約を追加する
4. rankings / detail / search のレスポンス整合をテストで固定する
5. A/B/D が共通利用できる Meta freshness helper を整理する

## 完了条件
- [ ] Meta 品質状態の契約が API で一貫する
- [ ] freshness と provenance が UI/監査に渡せる
- [ ] 回帰テストがある
