# D100: Real Metrics Ingestion Pipeline

## 優先度
- `P0`

## 目的
- 実データ数値が継続的に入ってくる ingestion 経路を強化する

## 対象
- `backend/app/tasks/metrics_tasks.py`
- `backend/app/tasks/crawl_tasks.py`
- `backend/app/services/crawling/`
- `backend/scripts/collect_real_metrics.py`
- `backend/scripts/run_live_ad_ingestion_wave.py`
- `backend/tests/`

## 実装タスク
1. 実データ源から `spend / impressions / reach / active status / LP final_url` の取り込み優先順位を明確化する
2. source ごとに `source_name`, `fetched_at`, `fetch_status`, `failure_reason` を保存する
3. stale 数値だけを再取得する lightweight path を追加する
4. ingestion 保存時に null 上書きを避け、より新しい実測値だけ反映する
5. C へ field mapping と freshness 条件を渡す

## 完了条件
- [ ] 実データ数値の取り込み経路が明確
- [ ] stale な数値だけ再取得できる
- [ ] ingestion 結果が provenance 付きで保存される

## ハンドオフ
- to C:
  - source field mapping
  - failure reason 一覧
- to A:
  - source 別 coverage 集計元データ
