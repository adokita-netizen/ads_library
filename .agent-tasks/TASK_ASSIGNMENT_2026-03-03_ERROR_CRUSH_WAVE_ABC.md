# Task Assignment (2026-03-03) — Error Crush Wave (A/B/C)

対象課題:
- 広告数が足りない
- 500/timeoutを含むエラーが頻発
- クロール完了後の反映不信感

## 優先順位
1. P0: quick-crawl系エラーの即時削減
2. P0: 日次広告件数の最低ライン達成
3. P0: UIクラッシュ/表示不整合の解消
4. P1: 契約テスト・E2Eで回帰防止

## Agent A
- タスク: `A40_ads_volume_recovery_and_error_zero.md`
- 到達目標:
  - 日次件数下限達成
  - データ保存失敗の再試行統一
  - 必須欠損の隔離

## Agent B
- タスク: `B46_frontend_error_crush_and_stable_refresh.md`
- 到達目標:
  - 主要導線のクラッシュゼロ
  - クロール後の最新反映を視覚/機能で保証
  - エラーメッセージ標準化

## Agent C
- タスク: `C42_api_error_crush_and_capacity_guard.md`
- 到達目標:
  - quick-crawl 500の原因コード化
  - 件数不足のフェイルソフト化
  - consistency APIで整合判定

## ハンドオフ順
1. C → B: `error_code` と quick-crawl契約確定
2. A → C: 件数監査しきい値・不足判定ルール確定
3. B → A/C: UI実測で残る失敗ケースをフィードバック

## DoD
- [ ] 直近3実行で quick-crawl 500率が許容値以下
- [ ] 日次広告件数が最低ラインを下回らない
- [ ] UIで「完了したのに古い」ケースが再現しない
- [ ] API契約テストとE2Eが通過

