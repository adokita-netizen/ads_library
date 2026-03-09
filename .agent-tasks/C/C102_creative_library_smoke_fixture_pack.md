# C102: Creative Library Smoke Fixture Pack

## 優先度: 🅱️ B（重要）

## 目的
- CRあり / DL不可 / LP欠損 / LP解決済み などの代表ケースを fixture 化し、E2E と契約テストの土台を共通化する

## 対象ファイル
- `backend/tests/`
- `.agent-tasks/API_CONTRACT_REGISTRY.md`

## 実装タスク
1. `downloadable`
2. `snapshot_only`
3. `lp_missing`
4. `lp_unresolved`
5. `lp_resolved_redirect`

上記ケースの fixture とレスポンス例を揃える

## 完了条件
- [ ] 契約テストと frontend smoke が同じ前提データを使える
- [ ] 代表ケースの見落としが減る
