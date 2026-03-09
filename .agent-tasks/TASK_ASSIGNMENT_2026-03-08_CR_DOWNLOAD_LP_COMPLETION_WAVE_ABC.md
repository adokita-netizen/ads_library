# TASK ASSIGNMENT: 2026-03-08 CR / Download / LP Completion Wave (ABC)

## 目的
- 広告ライブラリを「CRをここで見れる」「そのままDLできる」「LP遷移先も確認できる」状態に完成させる

## Agent A
- `A102_creative_download_lp_gap_audit_and_priority_queue.md`
- 役割:
  - CR / DL / LP 欠損率の監査
  - 復旧優先広告 Top N の算出
  - 改善効果の数値追跡

## Agent B
- `B93_creative_library_lp_preview_and_download_outcome_ui.md`
- 役割:
  - 一覧/詳細で CR / DL / LP 状態を即判別できる UI
  - 直接DLと一括DL結果の明示
  - LP 遷移先リンクの導線完成

## Agent C
- `C98_creative_media_and_lp_contract_completion.md`
- 役割:
  - `media_status`, `lp_info`, `bulk-download` 契約の完成
  - reason code の統一
  - API 契約書更新

## 実行順
1. C98
2. B93
3. A102

## 依存
- D97 の snapshot -> downloadable recovery を前提にする
- C98 が先に契約を固定し、B93 が UI に反映、A102 が改善率を監査する
