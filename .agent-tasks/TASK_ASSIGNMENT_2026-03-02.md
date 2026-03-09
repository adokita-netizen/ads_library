# Task Assignment (2026-03-02)

## 今日の方針
- P0/P1優先、依存ブロックを作らない順で進行。
- 作業開始時に `ROUND2_PROGRESS_TRACKER.md` を `IN_PROGRESS` へ更新。
- 完了時に `status.md` と `ROUND2_PROGRESS_TRACKER.md` を `DONE` へ更新。

## Wave 1 (配布済み)

### Agent A (Planner 1)
1. A-R2-1 Production Data Quality Fix (P0)
2. A-R2-4 DB Retry Unification / CI-001 (P0)

### Agent B (Planner 3)
1. B-R2-1 Dark Mode (P1)
2. B-R2-3 ProRanking UX Enhancement (P1)

### Agent C (Planner 2)
1. C-R2-4 N+1 Fix / CI-013 (P0)
2. C-R2-5 Pagination Limits / CI-014 (P0)

### Agent D (Planner 1)
1. D-R2-1 Scheduled Crawl (P0)
2. D-R2-2 Video Processing (P0)

## Wave 2 (追加配布)

### Agent A 追加
1. A-R2-2 Metrics Delta Tracking (P0)
2. A-R2-5 Metadata Validation / CI-007 (P0)

### Agent B 追加
1. B-R2-2 Heatmap Visualization (P1)
2. B-R2-4 Genre Filter Dashboard (P1)

### Agent C 追加
1. C-R2-1 AI Chat API (P0)
2. C-R2-2 Notification API (P0)

### Agent D 追加
1. D-R2-3 Media Precision (P1)
2. D-R2-4 LP Crawler (P1)

## ハンドオフ
- A/D 完了後に C へデータ更新通知。
- C のAPI変更が入る場合は B へ契約差分共有。

## ブロッカー対応
- Meta APIトークン等で停止した場合は `BLOCKED` 明記し、代替タスクへ切替。
