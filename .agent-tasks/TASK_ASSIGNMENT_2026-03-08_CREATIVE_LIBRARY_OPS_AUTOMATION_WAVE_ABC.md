# TASK ASSIGNMENT: 2026-03-08 Creative Library Ops Automation Wave (ABC)

## 目的
- Creative Library を「実装したら終わり」にせず、運用で品質維持できる状態にする

## Agent A
- `A104_creative_library_slo_and_ops_alerts.md`
- 役割:
  - SLO 設定
  - 悪化検知
  - 運用アラート候補の出力

## Agent B
- `B96_recovery_queue_and_manual_retry_ui.md`
- `B97_creative_library_regression_dashboard.md`
- 役割:
  - 復旧待ち UI
  - 回帰監視ダッシュボード
  - 手動再試行の受け皿

## Agent C
- `C101_recovery_trigger_api_and_operation_contract.md`
- `C102_creative_library_smoke_fixture_pack.md`
- 役割:
  - 再取得 API 契約
  - smoke/contract 共通 fixture

## 実行順
1. C101
2. C102
3. B96
4. B97
5. A104
