# D99: Live Ad Ingestion Reliability & Backfill Wave

## 優先度: 🅰️ A（クリティカル）

## 目的
- 新規流入が止まった時に自動で立て直せるよう、失敗再試行と backfill を強化する

## 対象ファイル
- `backend/app/tasks/crawl_tasks.py`
- `backend/app/tasks/media_tasks.py`
- `backend/scripts/`
- `backend/app/services/crawling/`

## 実装タスク
1. crawl 失敗時の `retry / defer / fallback` を新着優先で最適化する
2. `pending_heavy` や `snapshot_only` の広告を backfill wave にまとめる
3. `new ads discovered but creative missing` のケースを優先復旧する
4. 失敗 reason と再試行結果を metadata に保存し、A の監査へ渡せるようにする

## 完了条件
- [ ] 新規広告流入が止まっても自動回復しやすい
- [ ] 新着だが未完成の広告を早く usable 状態へ寄せられる
- [ ] 再試行の結果を監査できる
