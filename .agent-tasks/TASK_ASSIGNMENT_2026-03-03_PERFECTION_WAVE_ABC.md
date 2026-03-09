# Task Assignment (2026-03-03) — Perfection Wave (A/B/C)

対象:
- クロール完了後の最新反映の信頼性向上
- 遷移先LP情報取得の精度向上
- UIの可読性/操作性改善（Store導線の削除含む）

## 優先順位
1. P0: クロール完了後の反映保証（API + UI）
2. P0: LP情報取得の可視化と失敗理由標準化
3. P1: UI簡素化とジャンル軸フィルタの見やすさ改善
4. P1: 回帰テスト整備

## Agent A
- タスク: `A39_data_freshness_lp_intelligence.md`
- 目的:
  - 鮮度メタデータ標準化
  - LP情報取得データの正規化
  - 日次監査ジョブ導入
- 成果物:
  - `audit_data_freshness.py`
  - `audit_crawl_search_consistency.py`
  - 鮮度/LPメタデータ仕様

## Agent B
- タスク: `B45_crawl_reflection_ui_simplification.md`
- 目的:
  - クロール後の即時反映UX固定
  - フィルタUI再設計（ジャンル中心）
  - Store関連UIの撤去
  - クロール検索窓の回帰防止
- 成果物:
  - AdLibrary UI整理
  - Sidebar導線整理
  - E2Eテスト更新

## Agent C
- タスク: `C41_quick_crawl_consistency_lp_api.md`
- 目的:
  - quick-crawl契約固定
  - crawl→search整合確認API
  - LP情報可視化API
  - 契約テスト追加
- 成果物:
  - rankings endpoint拡張
  - API契約テスト
  - error_code辞書更新

## ハンドオフ順
1. C → B: quick-crawl返却契約とconsistency API確定
2. A → C: 鮮度/LPメタデータキー確定
3. B → A/C: UI上で必要な最終表示項目フィードバック

## DoD
- [ ] クロール完了後に最新反映がUI/APIの両方で検証済み
- [ ] LP情報取得の成功/失敗理由をAPIで観測可能
- [ ] UIが簡潔で、主要導線が1往復で操作可能
- [ ] E2E + API契約テストが通過し、回帰防止が効く

