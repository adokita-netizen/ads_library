# D96: Creative Library Recovery & Download Completeness

## 優先度: 🅰️ A（クリティカル）

## 問題
- UI導線を整えても、素材自体が不足している広告は「見れない・DLできない」
- `thumbnail はあるが image/video が無い`, `snapshot はあるが保存素材が無い` などの半端状態を減らす必要がある
- DL成功率を上げるには、取得優先順位と再回収フローを明示して実装する必要がある

## 対象ファイル
- `backend/app/services/media_extraction.py`
- `backend/app/tasks/media_tasks.py`
- `backend/scripts/backfill_media_urls.py`
- `backend/scripts/update_media_status.py`

## 実装方針

### 1. 復旧優先順位を固定
1. 既存S3キー確認
2. local cache確認
3. original image/video URL 再取得
4. snapshot から on-demand extract
5. browser fallback

### 2. 完全性スコアを上げる
- `viewable only`
- `downloadable`
- `downloadable + lp`
を分類し、`downloadable` 未満を重点復旧対象にする

### 3. 状態更新を明示
- `media_extraction_status`
- `media_completeness_score`
- `media_quality_issues`
- `last_recovery_attempt_at`

### 4. リカバリーバッチ
- `downloadable = false` の広告を一定件数ずつ再処理
- 成功時は最終取得元を残す
- 失敗時は理由を標準コードで残す

## 完了条件
- [x] `downloadable = false` の広告数を継続的に減らせる
- [x] snapshot only 状態からの復旧フローがある
- [x] 再回収結果が status/metadata に残る
- [x] UIが参照できる素材完全性の基礎データが揃う

## 制約
- Agent A/C 所有の指標計算やAPI契約を壊さない
- 重い browser fallback は通常経路失敗時のみ実行する

## 2026-03-10 完了メモ

- `backend/app/tasks/media_tasks.py`
  - `extract_media_task` に direct snapshot capture fallback を追加。
  - `MediaExtractor` が素材URLも screenshot_bytes も返せないケースでも、専用 browser session で再撮影して `image_s3_key / thumbnail_s3_key` を保存可能にした。
- `backend/app/tasks/lp_tasks.py`
  - 到達不能LPだけでなく、`destination_url` 自体が存在しない広告も terminal state として `ad_metadata.lp_terminal` / `lp_data` に同期できる前提を整備。
- `backend/scripts/recover_creative_lp_completeness.py`
  - `--terminal-limit` を追加し、destination URL 不在広告を terminal LP state として解決済みに正規化可能にした。
- `backend/scripts/audit_creative_lp_completeness.py`
  - raw 指標に加えて、terminal LP state を解決済みとして扱う `resolved_*` 指標を追加。
- `backend/scripts/report_missing_creatives.py`
  - 残存する未downloadable creative を即確認できるレポートスクリプトを追加。

## 最新確認値

- `downloadable_creative_rate: 100.00%`
- `thumbnail_rate: 100.00%`
- `image_rate: 100.00%`
- `lp_metadata_rate: 100.00%`
- `lp_content_rate: 100.00%`
- `resolved_full_rate: 100.00%`
- `full_completion_rate: 95.77%`

注記:
- `full_completion_rate` の未達分は、失敗LPではなく「元広告に destination URL が存在しない 93 件」。
- これらは terminal LP state として正規化済みで、運用上の completeness は `resolved_full_rate` を正とする。

## 未解決 / 次回の最優先

1. GitHub Actions の `Deploy VAAP` 実行権限が現ユーザーで拒否される問題を解消する。
2. 権限解消後に `Deploy VAAP` を手動起動し、run 完了まで確認する。
3. 必要なら raw 指標 (`full_completion_rate`) と resolved 指標 (`resolved_full_rate`) のUI表示方針を Agent B/C と同期する。
