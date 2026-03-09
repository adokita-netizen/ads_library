# D101: Real Metrics Backfill & Scheduler

## 優先度
- `P0`

## 目的
- 実数値が未取得・古い広告に対して、backfill と定期実行で継続改善できるようにする

## 対象
- `backend/scripts/scheduled_crawl_runner.py`
- `backend/scripts/run_live_ad_ingestion_wave.py`
- `backend/app/tasks/freshness_tasks.py`
- `backend/app/tasks/ops_tasks.py`
- `terraform/eventbridge.tf`
- `backend/tests/`

## 実装タスク
1. `estimated_only` と `stale_real_metrics` を対象にした backfill job を追加する
2. A の `priority_backfill_targets` を入力に使えるようにする
3. 定期ジョブで `high value ads` を優先して実測値更新する
4. 失敗時に retry / cooldown / partial success を分けて記録する
5. 実行結果を A の日次 report に渡せる summary JSON で出す

## 完了条件
- [ ] backfill 対象が自動で回る
- [ ] stale / estimated_only の広告が日次で改善される
- [ ] 失敗理由と retry 状態が可視化される

## ハンドオフ
- to A:
  - backfill 実行結果 summary
- to C:
  - scheduler / backfill response shape
