# B55: Crawl Result Clarity UI

## Objective
クロール結果表示を明確化し、「完了したが反映なし」を判別しやすくする。

## Scope
- Crawl modal 成功メッセージを `取得件数/保存件数/無効スキップ件数` で表示
- 失敗時は `failure_reason/error_code` を先頭表示
- 保存0件は warning 扱いで通知

## Acceptance Criteria
- 500時に失敗理由をユーザーが読める
- 保存0件時に成功トーストにならない
- 保存件数>0時は既存の成功導線を維持

## Status
Completed (2026-03-03)
