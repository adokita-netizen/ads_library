# D102: Japanese Gate Ingestion & Quarantine

## 優先度
- `P0`

## 目的
- 日本語広告以外が主分析へ流入し続ける状態を止める

## 対象
- `backend/app/tasks/crawl_tasks.py`
- `backend/app/tasks/metrics_tasks.py`
- `backend/scripts/run_live_ad_ingestion_wave.py`
- `backend/tests/`

## 実装タスク
1. ingest 時に `jp_char_ratio` を計算する
2. non-JP 候補は `exclude_from_analysis` or quarantine に送る
3. unknown は Bedrock 判定待ちキューに回す
4. quarantine reason を保存する
5. A に渡す review queue を出力する

## 完了条件
- [ ] 日本語以外が自動で主分析に入りにくい
- [ ] quarantine と unknown が分離される
- [ ] 後続の分類に必要な証跡が残る
